import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.messaging.rabbitmq import publish_event
from app.models.agenda import DomainEventOutbox


logger = logging.getLogger(__name__)
_stop_event = threading.Event()
_thread: threading.Thread | None = None


def utcnow():
    return datetime.now(timezone.utc)


def routing_enabled(routing_key: str) -> bool:
    flag = f"{routing_key.upper().replace('.', '_')}_ENABLED"
    return os.getenv(flag, "false").lower() == "true"


def enqueue_event(db, routing_key: str, payload: dict) -> DomainEventOutbox:
    """Persiste siempre; el feature flag controla despacho, no retención."""
    event_id = uuid.UUID(str(payload["event_id"]))
    row = DomainEventOutbox(
        event_id=event_id, routing_key=routing_key, payload=payload,
    )
    db.add(row)
    return row


def process_pending_events(limit: int = 50) -> int:
    db = SessionLocal()
    published = 0
    try:
        pending_keys = [row[0] for row in db.query(DomainEventOutbox.routing_key).filter(
            DomainEventOutbox.status.in_(("pending", "error")),
        ).distinct().all()]
        enabled_keys = [routing_key for routing_key in pending_keys if routing_enabled(routing_key)]
        if not enabled_keys:
            return 0
        rows = db.query(DomainEventOutbox).filter(
            DomainEventOutbox.status.in_(("pending", "error")),
            DomainEventOutbox.next_attempt_at <= utcnow(),
            DomainEventOutbox.routing_key.in_(enabled_keys),
        ).order_by(DomainEventOutbox.created_at).limit(limit).all()
        for row in rows:
            row.status = "processing"
            db.commit()
            try:
                publish_event(row.routing_key, row.payload)
                row.status = "done"
                row.published_at = utcnow()
                row.last_error = None
                db.commit()
                published += 1
            except Exception as exc:
                db.rollback()
                row = db.query(DomainEventOutbox).filter(DomainEventOutbox.id == row.id).one()
                row.attempts += 1
                row.last_error = str(exc)[:2000]
                if row.attempts >= 12:
                    row.status = "dead"
                else:
                    row.status = "error"
                    row.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 2 ** row.attempts))
                db.commit()
                logger.warning("No se pudo publicar evento %s: %s", row.event_id, exc)
    finally:
        db.close()
    return published


def _loop():
    interval = max(2, int(os.getenv("AGENDA_EVENT_OUTBOX_POLL_SECONDS", "10")))
    while not _stop_event.is_set():
        try:
            process_pending_events()
        except Exception:
            logger.exception("Error no controlado en outbox de eventos de Agenda")
        _stop_event.wait(interval)


def start_event_outbox():
    global _thread
    if os.getenv("AGENDA_EVENT_OUTBOX_ENABLED", "true").lower() != "true":
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="agenda-event-outbox", daemon=True)
    _thread.start()


def stop_event_outbox():
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=3)
