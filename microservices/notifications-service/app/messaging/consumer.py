import json
import time

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services import (
    DuplicateEventError,
    InvalidPayloadError,
    persist_processed_event,
    process_event,
)


RETRYABLE_EXCEPTIONS = (pika.exceptions.AMQPError, OSError, RuntimeError)


def create_connection_parameters() -> pika.ConnectionParameters:
    credentials = pika.PlainCredentials(
        settings.RABBITMQ_USER,
        settings.RABBITMQ_PASS,
    )
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=30,
        connection_attempts=1,
        socket_timeout=10,
    )


def _process_delivery(
    channel: BlockingChannel,
    method: Basic.Deliver,
    body: bytes,
) -> None:
    db: Session | None = None

    try:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise InvalidPayloadError("El payload JSON debe ser un objeto.")

        action_summary = process_event(method.routing_key, payload)
        db = SessionLocal()
        persist_processed_event(db, method.routing_key, payload, action_summary)
    except DuplicateEventError:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    except InvalidPayloadError:
        if db is not None:
            db.rollback()
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
    except json.JSONDecodeError:
        if db is not None:
            db.rollback()
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
    except RETRYABLE_EXCEPTIONS:
        if db is not None:
            db.rollback()
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    except Exception:
        if db is not None:
            db.rollback()
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    finally:
        if db is not None:
            db.close()

    channel.basic_ack(delivery_tag=method.delivery_tag)


def consume_forever() -> None:
    parameters = create_connection_parameters()
    backoff_seconds = 5

    while True:
        connection = None

        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.exchange_declare(
                exchange=settings.RABBITMQ_EXCHANGE,
                exchange_type="topic",
                durable=True,
            )
            channel.exchange_declare(
                exchange=settings.RABBITMQ_DLX,
                exchange_type="topic",
                durable=True,
            )
            channel.queue_declare(queue=settings.RABBITMQ_DLQ, durable=True)
            channel.queue_bind(
                exchange=settings.RABBITMQ_DLX,
                queue=settings.RABBITMQ_DLQ,
                routing_key="notifications.rejected",
            )
            channel.queue_declare(
                queue=settings.RABBITMQ_QUEUE,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": settings.RABBITMQ_DLX,
                    "x-dead-letter-routing-key": "notifications.rejected",
                },
            )
            channel.queue_bind(
                exchange=settings.RABBITMQ_EXCHANGE,
                queue=settings.RABBITMQ_QUEUE,
                routing_key=settings.RABBITMQ_BINDING_KEY,
            )
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=settings.RABBITMQ_QUEUE,
                on_message_callback=lambda ch, method, properties, body: _process_delivery(
                    ch,
                    method,
                    body,
                ),
                auto_ack=False,
            )

            backoff_seconds = 5
            channel.start_consuming()
        except KeyboardInterrupt:
            break
        except Exception:
            pass
        finally:
            if connection is not None:
                try:
                    if connection.is_open:
                        connection.close()
                except Exception:
                    pass

        time.sleep(backoff_seconds)
        backoff_seconds = min(backoff_seconds * 2, 30)


def start_consumer() -> None:
    consume_forever()


if __name__ == "__main__":
    start_consumer()
