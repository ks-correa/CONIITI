from typing import Any

import httpx

from app.config import settings


def _auth_headers() -> dict[str, str]:
    return {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}


def create_auth_account(payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"{settings.AUTH_SERVICE_URL}/internal/users",
        json=payload,
        headers=_auth_headers(),
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def update_auth_account(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.patch(
        f"{settings.AUTH_SERVICE_URL}/internal/users/{user_id}",
        json=payload,
        headers=_auth_headers(),
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def revoke_auth_sessions(user_id: str, *, is_active: bool | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if is_active is not None:
        payload["is_active"] = is_active
    response = httpx.post(
        f"{settings.AUTH_SERVICE_URL}/internal/users/{user_id}/revoke-sessions",
        json=payload,
        headers=_auth_headers(),
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def introspect_token(token: str) -> dict[str, Any]:
    response = httpx.post(
        f"{settings.AUTH_SERVICE_URL}/internal/introspect",
        json={"token": token},
        headers=_auth_headers(),
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()


def delete_auth_account(user_id: str) -> None:
    response = httpx.delete(
        f"{settings.AUTH_SERVICE_URL}/internal/users/{user_id}",
        headers=_auth_headers(),
        timeout=10.0,
    )
    if response.status_code not in (204, 404):
        response.raise_for_status()
