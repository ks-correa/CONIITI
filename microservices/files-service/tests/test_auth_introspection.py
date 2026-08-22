import asyncio
import uuid

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.utils import security


def request_with_token():
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/assets",
        "headers": [(b"authorization", b"Bearer opaque-access-token-value")],
    })


def request_with_cookie_without_origin():
    return Request({
        "type": "http",
        "method": "PUT",
        "path": "/site-config",
        "headers": [(b"cookie", b"access_token=opaque-access-token-value"), (b"host", b"coniiti.test")],
    })


def test_auth_unavailable_fails_closed(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("auth offline")

    monkeypatch.setattr(security.httpx, "AsyncClient", FailingClient)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.get_current_user(request_with_token()))
    assert exc.value.status_code == 503


def test_revoked_session_is_rejected(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"active": False}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(security.httpx, "AsyncClient", Client)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.get_current_user(request_with_token()))
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"active": True, "user_id": "invalid", "role": "staff", "session_version": 1},
        {"active": True, "user_id": str(uuid.uuid4()), "role": "owner", "session_version": 1},
        {"active": True, "user_id": str(uuid.uuid4()), "role": "staff", "session_version": False},
    ],
)
def test_malformed_active_contract_fails_closed(monkeypatch, payload):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(security.httpx, "AsyncClient", Client)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.get_current_user(request_with_token()))
    assert exc.value.status_code == 503


def test_cookie_mutation_rejects_missing_origin():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.get_current_user(request_with_cookie_without_origin()))
    assert exc.value.status_code == 403
