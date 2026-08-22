import asyncio
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
            "path": "/stats",
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


class _AsyncClient:
    def __init__(self, payload, *_, **__):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, *_, **__):
        if isinstance(self.payload, Exception):
            raise self.payload
        return _Response(self.payload)


def test_introspection_normalizes_superuser(monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClient(
            {
                "active": True,
                "user_id": str(user_id),
                "role": " SUPERUSER ",
                "session_version": 4,
            },
            *args,
            **kwargs,
        ),
    )

    current = asyncio.run(security.get_current_user(_request()))

    assert current.id == str(user_id)
    assert current.role == "superuser"
    assert current.session_version == 4


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [({"active": False}, 401), (["malformed"], 503)],
)
def test_introspection_rejects_inactive_or_malformed_contract(monkeypatch, payload, expected_status):
    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClient(payload, *args, **kwargs),
    )

    with pytest.raises(HTTPException) as captured:
        asyncio.run(security.get_current_user(_request()))

    assert captured.value.status_code == expected_status


def test_introspection_timeout_fails_closed(monkeypatch):
    timeout = httpx.ConnectTimeout("auth timeout")
    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClient(timeout, *args, **kwargs),
    )

    with pytest.raises(HTTPException) as captured:
        asyncio.run(security.get_current_user(_request()))

    assert captured.value.status_code == 503
