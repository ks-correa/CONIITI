from dataclasses import dataclass
import secrets
import uuid

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt

from app.config import settings
from app.clients import auth_client
import httpx


@dataclass
class AuthenticatedUser:
    id: str
    email: str | None
    full_name: str | None
    role: str
    session_version: int | None = None


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]

    token_from_cookie = request.cookies.get("access_token")
    if token_from_cookie:
        return token_from_cookie

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de acceso requerido.",
    )


def get_current_user(request: Request) -> AuthenticatedUser:
    token = _extract_token(request)

    if settings.AUTH_INTROSPECTION_ENABLED:
        try:
            payload = auth_client.introspect_token(token)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No fue posible validar la sesion en auth-service.",
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
            email=payload.get("email"),
            full_name=payload.get("full_name"),
            role=role.strip().lower(),
            session_version=session_version,
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado.",
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido.",
        )

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token incompleto.",
        )

    return AuthenticatedUser(
        id=user_id,
        email=payload.get("email"),
        full_name=payload.get("full_name"),
        role=str(role),
        session_version=payload.get("sv"),
    )


def require_superuser(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if current_user.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de superusuario.",
        )
    return current_user


def require_internal_request(
    x_internal_service_token: str | None = Header(default=None),
) -> None:
    if not x_internal_service_token or not secrets.compare_digest(
        x_internal_service_token,
        settings.INTERNAL_SERVICE_TOKEN,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solicitud interna no autorizada.",
        )
