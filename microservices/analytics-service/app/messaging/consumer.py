import asyncio
import json
import logging
import os

import aio_pika

from app.database import events_collection


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "shared-rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "local-dev-rabbitmq-password")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "coniiti_events")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "analytics_queue_v2")
RABBITMQ_BINDING_KEY = os.getenv("RABBITMQ_BINDING_KEY", "#")
RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "coniiti_events_dlx")
RABBITMQ_DLQ = os.getenv("RABBITMQ_DLQ", "analytics_dead_letter")


async def save_to_mongo(data: dict) -> None:
    await events_collection.update_one(
        {"event_id": data["event_id"]},
        {"$setOnInsert": data},
        upsert=True,
    )


def _decode_event(message: aio_pika.IncomingMessage) -> dict:
    try:
        event_data = json.loads(message.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El mensaje no contiene un objeto JSON valido.") from exc
    if not isinstance(event_data, dict):
        raise ValueError("El payload analytics debe ser un objeto JSON.")

    event_id = event_data.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 64:
        raise ValueError("event_id es obligatorio y admite hasta 64 caracteres.")

    routing_key = str(getattr(message, "routing_key", "") or "").strip()
    event_name = event_data.get("event")
    if routing_key:
        if event_name is not None and event_name != routing_key:
            raise ValueError("El tipo del envelope no coincide con la routing key.")
        event_data["event"] = routing_key
    elif not isinstance(event_name, str) or not event_name.strip():
        raise ValueError("event es obligatorio cuando no existe routing key.")
    event_data["event_id"] = event_id.strip()
    return event_data


async def process_message(message: aio_pika.IncomingMessage) -> None:
    try:
        event_data = _decode_event(message)
    except ValueError as exc:
        logging.getLogger(__name__).warning("Evento analytics rechazado: %s", exc)
        await message.reject(requeue=False)
        return

    try:
        await save_to_mongo(event_data)
    except Exception as exc:
        logging.getLogger(__name__).error("Error persistiendo evento analytics: %s", exc)
        await message.nack(requeue=True)
        return
    await message.ack()


async def start_consumer() -> None:
    retry_delay_seconds = 5

    while True:
        try:
            connection = await aio_pika.connect_robust(
                host=RABBITMQ_HOST,
                login=RABBITMQ_USER,
                password=RABBITMQ_PASS,
            )
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                exchange = await channel.declare_exchange(
                    RABBITMQ_EXCHANGE,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                dlx = await channel.declare_exchange(
                    RABBITMQ_DLX,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                dead_letter_queue = await channel.declare_queue(RABBITMQ_DLQ, durable=True)
                await dead_letter_queue.bind(dlx, routing_key="analytics.rejected")
                queue = await channel.declare_queue(
                    RABBITMQ_QUEUE,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": RABBITMQ_DLX,
                        "x-dead-letter-routing-key": "analytics.rejected",
                    },
                )
                await queue.bind(exchange, routing_key=RABBITMQ_BINDING_KEY)
                await queue.consume(process_message)

                await asyncio.Future()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.getLogger(__name__).error("No se pudo conectar analytics-service a RabbitMQ: %s", exc)
            await asyncio.sleep(retry_delay_seconds)
