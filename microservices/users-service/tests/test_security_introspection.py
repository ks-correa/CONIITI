import uuid

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.clients import auth_client
from app.config import settings
from app.utils.security import get_current_user


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/me",
        "headers": [(b"authorization", b"Bearer signed-token")],
    })


def test_introspection_normalizes_valid_contract(monkeypatch):
    user_id = str(uuid.uuid4())
    monkeypatch.setattr(settings, "AUTH_INTROSPECTION_ENABLED", True)
    monkeypatch.setattr(
        auth_client,
        "introspect_token",
        lambda _token: {
            "active": True,
            "user_id": user_id,
            "email": "person@example.org",
            "full_name": "Person",
            "role": " SUPERUSER ",
            "session_version": 2,
        },
    )

    current = get_current_user(_request())

    assert current.id == user_id
    assert current.role == "superuser"
    assert current.session_version == 2


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"active": True, "user_id": "not-a-uuid", "role": "external", "session_version": 1},
        {"active": True, "user_id": str(uuid.uuid4()), "role": "owner", "session_version": 1},
        {"active": True, "user_id": str(uuid.uuid4()), "role": "external", "session_version": True},
    ],
)
def test_introspection_rejects_malformed_active_contract(monkeypatch, payload):
    monkeypatch.setattr(settings, "AUTH_INTROSPECTION_ENABLED", True)
    monkeypatch.setattr(auth_client, "introspect_token", lambda _token: payload)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request())

    assert exc_info.value.status_code == 503


def test_introspection_fails_closed_when_auth_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTROSPECTION_ENABLED", True)

    def unavailable(_token):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(auth_client, "introspect_token", unavailable)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request())

    assert exc_info.value.status_code == 503
