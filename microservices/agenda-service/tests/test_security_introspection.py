import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.utils import security


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def request_with_token(token: str = "opaque-auth-token") -> Request:
    return Request({
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    })


def test_real_auth_introspection_shape_normalizes_user_id(monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setenv("AUTH_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:8000")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "secret")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {
            "active": True,
            "user_id": str(user_id),
            "role": " STAFF ",
            "session_version": 2,
            "type": "access",
        }),
    )
    payload = security.introspect_token("signed-token")
    assert security._normalized_subject(payload) == str(user_id)
    assert payload["role"] == "staff"
    assert payload["session_version"] == 2


def test_active_guard_delegates_signature_validation_to_auth(monkeypatch):
    expected = {
        "active": True,
        "user_id": str(uuid.uuid4()),
        "role": "external",
        "session_version": 1,
    }
    monkeypatch.setattr(security, "introspect_token", lambda token: expected)

    assert security._active_payload(request_with_token()) == expected


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"active": True, "user_id": "not-a-uuid", "role": "external", "session_version": 1},
        {
            "active": True,
            "user_id": str(uuid.uuid4()),
            "role": "",
            "session_version": 1,
        },
        {
            "active": True,
            "user_id": str(uuid.uuid4()),
            "role": "owner",
            "session_version": 1,
        },
        {
            "active": True,
            "user_id": str(uuid.uuid4()),
            "role": "external",
            "session_version": True,
        },
        {
            "active": True,
            "user_id": str(uuid.uuid4()),
            "role": "external",
            "session_version": 0,
        },
        {
            "active": True,
            "user_id": str(uuid.uuid4()),
            "role": "external",
            "session_version": "1",
        },
    ],
)
def test_introspection_rejects_malformed_active_contract(monkeypatch, payload):
    monkeypatch.setenv("AUTH_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:8000")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "secret")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(200, payload),
    )

    with pytest.raises(HTTPException) as error:
        security.introspect_token("signed-token")

    assert error.value.status_code == 503


def test_introspection_keeps_inactive_session_as_unauthorized(monkeypatch):
    monkeypatch.setenv("AUTH_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:8000")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "secret")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {"active": False}),
    )

    with pytest.raises(HTTPException) as error:
        security.introspect_token("signed-token")

    assert error.value.status_code == 401


def test_introspection_fails_closed_when_auth_is_unavailable(monkeypatch):
    monkeypatch.setenv("AUTH_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:8000")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "secret")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(security.httpx.ConnectError("down")),
    )
    with pytest.raises(HTTPException) as error:
        security.introspect_token("signed-token")
    assert error.value.status_code == 503
