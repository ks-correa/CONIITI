import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.agenda import ResourceState, Venue, VenueResource
from app.repositories.venue_repository import VenueRepository
from app.schemas.venue import VenueCreate, VenueResourceCreate, VenueResourceUpdate, VenueUpdate


def _now():
    return datetime.now(timezone.utc)


def _venue_or_404(venue_id: uuid.UUID, repo: VenueRepository, for_update: bool = False):
    venue = repo.get(venue_id, for_update=for_update)
    if not venue:
        raise HTTPException(status_code=404, detail="Sede no encontrada.")
    return venue


def _validate_external_host(url: str | None) -> None:
    if not url or (url.startswith("/") and not url.startswith("//")):
        return
    allowed = {host.strip().lower() for host in os.getenv("AGENDA_MEDIA_ALLOWED_HOSTS", "").split(",") if host.strip()}
    if not allowed:
        raise HTTPException(
            status_code=422,
            detail="Los proveedores multimedia externos no están habilitados; usa un asset de Files.",
        )
    if (urlparse(url).hostname or "").lower() not in allowed:
        raise HTTPException(status_code=422, detail="Proveedor multimedia externo no permitido.")


def list_venues(repo: VenueRepository, include_inactive: bool = False):
    return repo.list(include_inactive=include_inactive)


def get_venue(venue_id: uuid.UUID, repo: VenueRepository):
    return _venue_or_404(venue_id, repo)


def create_venue(data: VenueCreate, actor_id: uuid.UUID, repo: VenueRepository):
    if repo.find_by_name(data.name):
        raise HTTPException(status_code=409, detail="Ya existe una sede con ese nombre.")
    venue = Venue(**data.model_dump(), created_by=actor_id)
    repo.db.add(venue)
    try:
        repo.commit()
    except IntegrityError as exc:
        repo.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una sede con ese nombre.") from exc
    return repo.get(venue.id)


def update_venue(venue_id: uuid.UUID, data: VenueUpdate, repo: VenueRepository):
    venue = _venue_or_404(venue_id, repo, for_update=True)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and repo.find_by_name(changes["name"], exclude_id=venue.id):
        raise HTTPException(status_code=409, detail="Ya existe una sede con ese nombre.")
    if "capacity" in changes and changes["capacity"] < repo.max_session_capacity(venue.id):
        raise HTTPException(status_code=409, detail="La capacidad es menor que los cupos de una sesión existente.")
    for field, value in changes.items():
        setattr(venue, field, value)
    venue.updated_at = _now()
    repo.commit()
    return repo.get(venue.id)


def delete_venue(venue_id: uuid.UUID, repo: VenueRepository):
    venue = _venue_or_404(venue_id, repo, for_update=True)
    if repo.count_sessions(venue.id):
        raise HTTPException(status_code=409, detail="La sede está referenciada por sesiones históricas.")
    venue.is_active = False
    venue.deleted_at = _now()
    venue.updated_at = _now()
    repo.commit()


def create_resource(
    venue_id: uuid.UUID, data: VenueResourceCreate,
    actor_id: uuid.UUID, repo: VenueRepository,
):
    _venue_or_404(venue_id, repo)
    _validate_external_host(data.external_url)
    _validate_external_host(data.captions_url)
    _validate_external_host(data.transcript_url)
    values = data.model_dump()
    state = (
        ResourceState.PENDING_ASSET.value
        if any((data.asset_id, data.captions_asset_id, data.transcript_asset_id))
        else ResourceState.ACTIVE.value
    )
    resource = VenueResource(
        **values, venue_id=venue_id, created_by=actor_id,
        state=state, resolved_url=data.external_url,
    )
    repo.db.add(resource)
    repo.flush()
    if data.asset_id:
        repo.queue_asset_operation(resource.id, data.asset_id, "claim", slot="primary")
    if data.captions_asset_id:
        repo.queue_asset_operation(
            resource.id, data.captions_asset_id, "claim", slot="captions",
        )
    if data.transcript_asset_id:
        repo.queue_asset_operation(
            resource.id, data.transcript_asset_id, "claim", slot="transcript",
        )
    repo.commit()
    return repo.get_resource(venue_id, resource.id)


def update_resource(
    venue_id: uuid.UUID, resource_id: uuid.UUID,
    data: VenueResourceUpdate, repo: VenueRepository,
):
    _venue_or_404(venue_id, repo)
    resource = repo.get_resource(venue_id, resource_id, for_update=True)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso de sede no encontrado.")
    changes = data.model_dump(exclude_unset=True)
    merged = {
        field: changes.get(field, getattr(resource, field))
        for field in (
            "resource_type", "title", "description", "alt_text", "asset_id",
            "external_url", "mime_type", "captions_asset_id", "captions_url",
            "transcript_asset_id", "transcript_url", "display_order", "is_active",
        )
    }
    # Cambiar una fuente limpia la otra, incluso si el cliente solo envía una.
    if "asset_id" in changes and changes["asset_id"] is not None:
        merged["external_url"] = None
    if "external_url" in changes and changes["external_url"] is not None:
        merged["asset_id"] = None
    if "captions_asset_id" in changes and changes["captions_asset_id"] is not None:
        merged["captions_url"] = None
    if "captions_url" in changes and changes["captions_url"] is not None:
        merged["captions_asset_id"] = None
    if "transcript_asset_id" in changes and changes["transcript_asset_id"] is not None:
        merged["transcript_url"] = None
    if "transcript_url" in changes and changes["transcript_url"] is not None:
        merged["transcript_asset_id"] = None
    validated = VenueResourceCreate(**merged)
    _validate_external_host(validated.external_url)
    _validate_external_host(validated.captions_url)
    _validate_external_host(validated.transcript_url)
    old_sources = {
        "primary": (resource.asset_id, resource.external_url),
        "captions": (resource.captions_asset_id, resource.captions_url),
        "transcript": (resource.transcript_asset_id, resource.transcript_url),
    }
    old_resource_type = resource.resource_type
    for field, value in validated.model_dump().items():
        setattr(resource, field, value)
    resource.updated_at = _now()

    primary_changed = (
        old_sources["primary"] != (validated.asset_id, validated.external_url)
        or old_resource_type != validated.resource_type.value
    )
    if primary_changed:
        resource.resolved_url = validated.external_url
        if validated.asset_id:
            resource.state = ResourceState.PENDING_ASSET.value
            repo.queue_asset_operation(
                resource.id, validated.asset_id, "claim", slot="primary",
            )
        if old_sources["primary"][0] and old_sources["primary"][0] != validated.asset_id:
            repo.queue_asset_operation(
                resource.id, old_sources["primary"][0], "release",
                finalize_delete=False, slot="primary",
            )

    supplemental = (
        (
            "captions", validated.captions_asset_id, validated.captions_url,
            "captions_resolved_url",
        ),
        (
            "transcript", validated.transcript_asset_id, validated.transcript_url,
            "transcript_resolved_url",
        ),
    )
    supplemental_changed = False
    current_asset_ids = {
        asset_id for asset_id in (
            validated.asset_id,
            validated.captions_asset_id,
            validated.transcript_asset_id,
        ) if asset_id
    }
    for slot, asset_id, external_url, resolved_field in supplemental:
        old_asset_id, old_external_url = old_sources[slot]
        if (old_asset_id, old_external_url) == (asset_id, external_url):
            continue
        supplemental_changed = True
        setattr(resource, resolved_field, None)
        if asset_id and asset_id != old_asset_id:
            repo.queue_asset_operation(resource.id, asset_id, "claim", slot=slot)
        if (
            old_asset_id
            and old_asset_id != asset_id
            and old_asset_id not in current_asset_ids
        ):
            repo.queue_asset_operation(
                resource.id, old_asset_id, "release",
                finalize_delete=False, slot=slot,
            )
    if primary_changed or supplemental_changed:
        unresolved_asset = any((
            resource.asset_id and not resource.resolved_url,
            resource.captions_asset_id and not resource.captions_resolved_url,
            resource.transcript_asset_id and not resource.transcript_resolved_url,
        ))
        resource.state = (
            ResourceState.PENDING_ASSET.value
            if unresolved_asset else ResourceState.ACTIVE.value
        )
    repo.commit()
    return repo.get_resource(venue_id, resource.id)


def delete_resource(venue_id: uuid.UUID, resource_id: uuid.UUID, repo: VenueRepository):
    _venue_or_404(venue_id, repo)
    resource = repo.get_resource(venue_id, resource_id, for_update=True)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso de sede no encontrado.")
    resource.is_active = False
    resource.updated_at = _now()
    assets_by_id = {}
    for slot, asset_id in (
        ("primary", resource.asset_id),
        ("captions", resource.captions_asset_id),
        ("transcript", resource.transcript_asset_id),
    ):
        if asset_id:
            assets_by_id.setdefault(asset_id, slot)
    if assets_by_id:
        resource.state = ResourceState.PENDING_DELETE.value
        for asset_id, slot in assets_by_id.items():
            repo.queue_asset_operation(
                resource.id, asset_id, "release", finalize_delete=True, slot=slot,
            )
    else:
        repo.tombstone(resource)
    repo.commit()
