from dataclasses import dataclass
import uuid

from fastapi import Depends, HTTPException, Request, status
import httpx

from .config import settings


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    role: str
    session_version: int


def get_current_user(request: Request) -> AuthenticatedUser:
    authorization = request.headers.get("Authorization", "")
    token = authorization.split(" ", 1)[1] if authorization.startswith("Bearer ") else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acceso requerido.")
    try:
        response = httpx.post(
            f"{settings.AUTH_SERVICE_URL.rstrip('/')}/internal/introspect",
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
            json={"token": token},
            timeout=3,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No se pudo validar la sesion.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio un contrato de introspeccion invalido.",
        )
    if payload.get("active") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion invalida, expirada o revocada.")

    role = payload.get("role")
    session_version = payload.get("session_version", 0)
    try:
        user_id = str(uuid.UUID(str(payload.get("user_id"))))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio un subject invalido.",
        ) from exc
    if (
        not isinstance(role, str)
        or not role.strip()
        or not isinstance(session_version, int)
        or isinstance(session_version, bool)
        or session_version < 0
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth devolvio metadatos de sesion invalidos.",
        )
    return AuthenticatedUser(
        id=user_id,
        role=role.strip().lower(),
        session_version=session_version,
    )


def require_superuser(current: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if current.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol de superusuario.")
    return current
