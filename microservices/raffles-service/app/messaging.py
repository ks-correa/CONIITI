import json
import logging
import threading
from datetime import datetime, timezone

import pika
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import OutboxEvent


logger = logging.getLogger(__name__)


def _connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=30,
            blocked_connection_timeout=15,
        )
    )


def dispatch_pending(db: Session, limit: int = 20) -> int:
    if not settings.PREMIO_ADJUDICADO_ENABLED:
        return 0
    pending = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )
    if not pending:
        return 0

    connection = None
    published = 0
    try:
        connection = _connection()
        channel = connection.channel()
        channel.exchange_declare(
            exchange=settings.RABBITMQ_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        channel.confirm_delivery()
        for event in pending:
            try:
                confirmed = channel.basic_publish(
                    exchange=settings.RABBITMQ_EXCHANGE,
                    routing_key=event.routing_key,
                    body=json.dumps(event.payload, separators=(",", ":"), default=str).encode("utf-8"),
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,
                        message_id=str(event.payload.get("event_id", event.id)),
                    ),
                    mandatory=True,
                )
                if confirmed is False:
                    raise RuntimeError("RabbitMQ no confirmo la publicacion del evento.")
                event.published_at = datetime.now(timezone.utc)
                event.attempts += 1
                event.last_error = None
                published += 1
            except Exception as exc:  # pragma: no cover - broker-specific failure
                event.attempts += 1
                event.last_error = str(exc)[:2000]
                logger.exception("No se pudo publicar evento outbox %s", event.id)
                break
        db.commit()
    except Exception as exc:  # broker unavailable: the durable row remains pending
        db.rollback()
        logger.warning("RabbitMQ no disponible; se conserva el outbox: %s", exc)
    finally:
        if connection is not None and connection.is_open:
            connection.close()
    return published


def outbox_worker(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            dispatch_pending(db)
        finally:
            db.close()
        stop_event.wait(5)


def start_outbox_worker(stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(
        target=outbox_worker,
        args=(stop_event,),
        daemon=True,
        name="raffles-outbox",
    )
    thread.start()
    return thread
