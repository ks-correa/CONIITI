import logging
import os
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_

from app.clients.files_client import (
    FilesClient,
    FilesIntegrationError,
    public_asset_url,
    validate_asset_type,
)
from app.database import SessionLocal
from app.models.agenda import AssetReferenceOutbox, ResourceState, VenueResource


logger = logging.getLogger(__name__)
MAX_ATTEMPTS = int(os.getenv("ASSET_REFERENCE_MAX_ATTEMPTS", "8"))
POLL_SECONDS = max(2, int(os.getenv("ASSET_REFERENCE_POLL_SECONDS", "15")))
PROCESSING_LEASE_SECONDS = max(
    30, int(os.getenv("ASSET_REFERENCE_PROCESSING_LEASE_SECONDS", "120")),
)
_stop_event = threading.Event()
_thread: threading.Thread | None = None

_SLOT_FIELDS = {
    "primary": ("asset_id", "resolved_url"),
    "captions": ("captions_asset_id", "captions_resolved_url"),
    "transcript": ("transcript_asset_id", "transcript_resolved_url"),
}


def _now():
    return datetime.now(timezone.utc)


def _slot_fields(slot: str) -> tuple[str, str]:
    try:
        return _SLOT_FIELDS[slot]
    except KeyError as exc:
        raise FilesIntegrationError(f"Slot de asset desconocido: {slot}") from exc


def _validate_slot_asset(resource: VenueResource, slot: str, asset: dict) -> str:
    if slot == "primary":
        return validate_asset_type(resource.resource_type, asset)

    mime_type = validate_asset_type("document", asset)
    if slot == "captions" and mime_type != "text/vtt":
        raise FilesIntegrationError("Los subtítulos alojados en Files deben usar MIME text/vtt.")
    if slot == "transcript" and not mime_type.startswith("text/"):
        raise FilesIntegrationError("La transcripción alojada en Files debe ser un archivo de texto.")
    return mime_type


def _refresh_resource_state(resource: VenueResource) -> None:
    unresolved = any(
        getattr(resource, asset_field) and not getattr(resource, resolved_field)
        for asset_field, resolved_field in _SLOT_FIELDS.values()
    )
    if not unresolved:
        resource.state = ResourceState.ACTIVE.value
    elif resource.state != ResourceState.ERROR.value:
        resource.state = ResourceState.PENDING_ASSET.value


def _resource_references_asset(resource: VenueResource, asset_id) -> bool:
    return any(
        getattr(resource, asset_field) == asset_id
        for asset_field, _ in _SLOT_FIELDS.values()
    )


def process_pending_asset_references(limit: int = 25, client: FilesClient | None = None) -> int:
    client = client or FilesClient()
    processed = 0
    db = SessionLocal()
    try:
        ready_at = _now()
        rows = db.query(AssetReferenceOutbox).filter(
            or_(
                AssetReferenceOutbox.status.in_(("pending", "error")),
                and_(
                    AssetReferenceOutbox.status == "processing",
                    AssetReferenceOutbox.next_attempt_at <= ready_at,
                ),
            ),
            AssetReferenceOutbox.next_attempt_at <= _now(),
        ).order_by(AssetReferenceOutbox.created_at).with_for_update(
            skip_locked=True,
        ).limit(limit).all()
        for row in rows:
            resource = db.query(VenueResource).filter(
                VenueResource.id == row.resource_id,
            ).with_for_update().first()
            if not resource:
                row.status = "done"
                row.processed_at = _now()
                db.commit()
                continue
            row.status = "processing"
            row.next_attempt_at = _now() + timedelta(seconds=PROCESSING_LEASE_SECONDS)
            db.commit()
            try:
                if row.operation == "claim":
                    asset_field, resolved_field = _slot_fields(row.slot)
                    if (
                        resource.deleted_at is not None
                        or getattr(resource, asset_field) != row.asset_id
                    ):
                        row.status = "done"
                        row.processed_at = _now()
                        db.commit()
                        processed += 1
                        continue
                    asset = client.lookup(row.asset_id)
                    mime_type = _validate_slot_asset(resource, row.slot, asset)
                    client.claim(row.asset_id, resource.id)
                    if row.slot == "primary":
                        resource.mime_type = mime_type
                    setattr(resource, resolved_field, public_asset_url(asset))
                    _refresh_resource_state(resource)
                elif row.operation == "release":
                    if row.finalize_delete or not _resource_references_asset(resource, row.asset_id):
                        client.release(row.asset_id, resource.id)
                    if row.finalize_delete:
                        resource.state = ResourceState.TOMBSTONED.value
                        resource.deleted_at = _now()
                        resource.is_active = False
                else:
                    raise RuntimeError(f"Operación de outbox desconocida: {row.operation}")
                row.status = "done"
                row.processed_at = _now()
                row.last_error = None
                db.commit()
                processed += 1
            except Exception as exc:  # El worker debe sobrevivir a fallos remotos.
                db.rollback()
                row = db.query(AssetReferenceOutbox).filter(AssetReferenceOutbox.id == row.id).one()
                resource = db.query(VenueResource).filter(VenueResource.id == row.resource_id).first()
                row.attempts += 1
                row.last_error = str(exc)[:2000]
                if row.attempts >= MAX_ATTEMPTS:
                    row.status = "dead"
                    slot_fields = _SLOT_FIELDS.get(row.slot)
                    if (
                        resource
                        and row.operation == "claim"
                        and slot_fields
                        and getattr(resource, slot_fields[0]) == row.asset_id
                        and resource.deleted_at is None
                    ):
                        resource.state = ResourceState.ERROR.value
                else:
                    row.status = "error"
                    delay = min(3600, 2 ** row.attempts)
                    row.next_attempt_at = _now() + timedelta(seconds=delay)
                db.commit()
                logger.warning("Falló reconciliación de asset %s: %s", row.asset_id, exc)
    finally:
        db.close()
    return processed


def _loop():
    while not _stop_event.is_set():
        try:
            process_pending_asset_references()
        except Exception:
            logger.exception("Error no controlado en reconciliador de assets")
        _stop_event.wait(POLL_SECONDS)


def start_asset_reconciler():
    global _thread
    if os.getenv("ASSET_REFERENCE_RECONCILER_ENABLED", "true").lower() != "true":
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="agenda-asset-reconciler", daemon=True)
    _thread.start()


def stop_asset_reconciler():
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=3)
