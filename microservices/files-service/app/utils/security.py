import os
import secrets
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, Request, status


MANAGE_FILES_ROLES = {"staff", "superuser"}
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    role: str
    email: str | None = None
    full_name: str | None = None


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]

    token_from_cookie = request.cookies.get("access_token")
    if token_from_cookie:
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            origin_host = urlparse(origin).netloc.lower() if origin else ""
            request_host = request.headers.get("Host", "").lower()
            configured = {
                item.strip().lower()
                for item in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
                if item.strip()
            }
            if not origin or (
                origin.rstrip("/").lower() not in configured
                and origin_host != request_host
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Origen no autorizado para una mutacion autenticada por cookie.",
                )
        return token_from_cookie

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de acceso requerido.",
    )


async def get_current_user(request: Request) -> AuthenticatedUser:
    token = _extract_token(request)
    internal_token = os.getenv("INTERNAL_SERVICE_TOKEN") or INTERNAL_SERVICE_TOKEN
    if not internal_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar la sesion.",
        )
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{os.getenv('AUTH_SERVICE_URL', AUTH_SERVICE_URL).rstrip('/')}/internal/introspect",
                headers={"X-Internal-Service-Token": internal_token},
                json={"token": token},
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar la sesion.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio un contrato de introspeccion invalido.",
        )
    if payload.get("active") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida, expirada o revocada.",
        )
    try:
        user_id = str(uuid.UUID(str(payload.get("user_id"))))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio un identificador de usuario invalido.",
        ) from exc
    role = payload.get("role")
    if not isinstance(role, str) or role.strip().lower() not in {
        "external",
        "university_community",
        "staff",
        "superuser",
    }:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio un rol invalido.",
        )
    session_version = payload.get("session_version")
    if not isinstance(session_version, int) or isinstance(session_version, bool) or session_version < 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio una version de sesion invalida.",
        )
    return AuthenticatedUser(
        id=user_id,
        role=role.strip().lower(),
        email=payload.get("email"),
        full_name=payload.get("full_name"),
    )


def require_files_manager(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if current_user.role not in MANAGE_FILES_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol staff o superuser.",
        )

    return current_user


def require_superuser(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if current_user.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol superuser.",
        )
    return current_user


def require_internal_service(request: Request) -> None:
    configured_token = os.getenv("INTERNAL_SERVICE_TOKEN") or INTERNAL_SERVICE_TOKEN
    provided_token = request.headers.get("X-Internal-Service-Token")
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticacion interna no configurada.",
        )
    if not provided_token or not secrets.compare_digest(provided_token, configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial interna invalida.",
        )
