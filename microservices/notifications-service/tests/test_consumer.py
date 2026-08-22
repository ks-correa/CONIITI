import json
from types import SimpleNamespace

from app.messaging import consumer
from app.services import DuplicateEventError


class _Channel:
    def __init__(self):
        self.acked = []
        self.nacked = []

    def basic_ack(self, delivery_tag):
        self.acked.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacked.append((delivery_tag, requeue))


class _Db:
    def rollback(self):
        return None

    def close(self):
        return None


def _method(routing_key: str):
    return SimpleNamespace(routing_key=routing_key, delivery_tag=7)


def test_valid_delivery_is_acknowledged(monkeypatch):
    channel = _Channel()
    persisted = []
    monkeypatch.setattr(consumer, "SessionLocal", _Db)
    monkeypatch.setattr(
        consumer,
        "persist_processed_event",
        lambda _db, routing_key, payload, summary: persisted.append(
            (routing_key, payload["event_id"], summary)
        ),
    )
    payload = {
        "event_id": "evt-1",
        "event": "premio.adjudicado",
        "raffle_id": "raffle-1",
        "winner_user_id": "user-1",
        "draw_number": 1,
        "drawn_at": "2026-08-21T10:00:00Z",
        "audit_hash": "a" * 64,
    }

    consumer._process_delivery(
        channel,
        _method("premio.adjudicado"),
        json.dumps(payload).encode(),
    )

    assert channel.acked == [7]
    assert channel.nacked == []
    assert persisted[0][0:2] == ("premio.adjudicado", "evt-1")


def test_invalid_delivery_is_dead_lettered():
    channel = _Channel()
    payload = {
        "event_id": "evt-2",
        "event": "asistencia.confirmada",
    }

    consumer._process_delivery(
        channel,
        _method("premio.adjudicado"),
        json.dumps(payload).encode(),
    )

    assert channel.acked == []
    assert channel.nacked == [(7, False)]


def test_duplicate_delivery_is_acknowledged_once(monkeypatch):
    channel = _Channel()
    monkeypatch.setattr(consumer, "SessionLocal", _Db)

    def duplicate(*_):
        raise DuplicateEventError

    monkeypatch.setattr(consumer, "persist_processed_event", duplicate)
    payload = {
        "event_id": "evt-3",
        "email": "user@example.test",
        "name": "User",
    }

    consumer._process_delivery(
        channel,
        _method("usuario.registrado"),
        json.dumps(payload).encode(),
    )

    assert channel.acked == [7]
    assert channel.nacked == []
