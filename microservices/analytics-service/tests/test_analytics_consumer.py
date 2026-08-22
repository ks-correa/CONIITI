import asyncio
import json

from app.messaging import consumer


class FakeIncomingMessage:
    def __init__(self, payload: bytes, routing_key: str = ""):
        self.body = payload
        self.routing_key = routing_key
        self.acked = False
        self.rejected = False
        self.requeued = None

    async def ack(self):
        self.acked = True

    async def reject(self, requeue: bool):
        self.rejected = True
        self.requeued = requeue

    async def nack(self, requeue: bool):
        self.requeued = requeue


def test_process_message_persists_json_object(monkeypatch):
    saved_events = []

    async def fake_save_to_mongo(data: dict) -> None:
        saved_events.append(data)

    monkeypatch.setattr(consumer, "save_to_mongo", fake_save_to_mongo)
    message = FakeIncomingMessage(
        json.dumps({"event_id": "evt-1", "event": "usuario.registrado"}).encode(),
        routing_key="usuario.registrado",
    )

    asyncio.run(consumer.process_message(message))

    assert saved_events == [{"event_id": "evt-1", "event": "usuario.registrado"}]
    assert message.acked is True


def test_process_message_ignores_invalid_json(monkeypatch):
    saved_events = []

    async def fake_save_to_mongo(data: dict) -> None:
        saved_events.append(data)

    monkeypatch.setattr(consumer, "save_to_mongo", fake_save_to_mongo)
    message = FakeIncomingMessage(b"{invalid-json")

    asyncio.run(consumer.process_message(message))

    assert saved_events == []
    assert message.rejected is True
    assert message.requeued is False


def test_process_message_rejects_envelope_routing_key_mismatch(monkeypatch):
    saved_events = []

    async def fake_save_to_mongo(data: dict) -> None:
        saved_events.append(data)

    monkeypatch.setattr(consumer, "save_to_mongo", fake_save_to_mongo)
    message = FakeIncomingMessage(
        json.dumps({"event_id": "evt-2", "event": "premio.adjudicado"}).encode(),
        routing_key="asistencia.confirmada",
    )

    asyncio.run(consumer.process_message(message))

    assert saved_events == []
    assert message.rejected is True
    assert message.requeued is False


def test_process_message_requeues_transient_storage_failure(monkeypatch):
    async def unavailable_storage(_: dict) -> None:
        raise RuntimeError("mongo unavailable")

    monkeypatch.setattr(consumer, "save_to_mongo", unavailable_storage)
    message = FakeIncomingMessage(
        json.dumps({"event_id": "evt-3", "event": "premio.adjudicado"}).encode(),
        routing_key="premio.adjudicado",
    )

    asyncio.run(consumer.process_message(message))

    assert message.acked is False
    assert message.rejected is False
    assert message.requeued is True
