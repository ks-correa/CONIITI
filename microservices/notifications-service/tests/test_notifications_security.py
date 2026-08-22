import uuid

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import security


def _request(token: str = "opaque-token") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
    )


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_introspection_normalizes_superuser(monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *_, **__: _Response(
            {
                "active": True,
                "user_id": str(user_id),
                "role": " SUPERUSER ",
                "session_version": 2,
            }
        ),
    )

    current = security.get_current_user(_request())

    assert current.id == str(user_id)
    assert current.role == "superuser"
    assert current.session_version == 2


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [({"active": False}, 401), (["malformed"], 503)],
)
def test_introspection_rejects_inactive_or_malformed_contract(monkeypatch, payload, expected_status):
    monkeypatch.setattr(security.httpx, "post", lambda *_, **__: _Response(payload))

    with pytest.raises(HTTPException) as captured:
        security.get_current_user(_request())

    assert captured.value.status_code == expected_status


def test_introspection_timeout_fails_closed(monkeypatch):
    def timeout(*_, **__):
        raise httpx.ConnectTimeout("auth timeout")

    monkeypatch.setattr(security.httpx, "post", timeout)

    with pytest.raises(HTTPException) as captured:
        security.get_current_user(_request())

    assert captured.value.status_code == 503
