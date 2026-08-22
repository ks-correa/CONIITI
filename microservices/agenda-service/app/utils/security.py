import os
import secrets
import uuid

import httpx
from fastapi import Header, HTTPException, Request, status
from jose import JWTError, jwt


SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Missing JWT_SECRET_KEY (or SECRET_KEY) environment variable.")
ALGORITHM = "HS256"
ALLOWED_ROLES = {
    "external",
    "university_community",
    "staff",
    "superuser",
}


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    token_from_cookie = request.cookies.get("access_token")
    if token_from_cookie:
        return token_from_cookie
    raise HTTPException(status_code=401, detail="Sesion no encontrada.")


def introspect_token(token: str) -> dict:
    """Consulta a Auth como fuente vigente de sesión y rol; ante duda falla cerrado."""
    if os.getenv("AUTH_INTROSPECTION_ENABLED", "true").lower() != "true":
        return decode_token(token)
    auth_url = os.getenv("AUTH_SERVICE_URL")
    internal_token = os.getenv("INTERNAL_SERVICE_TOKEN")
    if not auth_url or not internal_token:
        raise HTTPException(status_code=503, detail="Validación central de sesión no configurada.")
    try:
        response = httpx.post(
            f"{auth_url.rstrip('/')}/internal/introspect",
            json={"token": token},
            headers={"X-Internal-Service-Token": internal_token},
            timeout=float(os.getenv("AUTH_SERVICE_TIMEOUT_SECONDS", "3")),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="No fue posible validar la sesión con Auth.") from exc
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail="Auth no está disponible para validar la sesión.")
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Sesión no válida.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Respuesta inválida de Auth.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="Auth devolvio un contrato de introspeccion invalido.")

    active = payload.get("active")
    if active is False:
        raise HTTPException(status_code=401, detail="Sesión inactiva o revocada.")
    if active is not True:
        raise HTTPException(status_code=503, detail="Auth devolvio un estado de sesion invalido.")

    try:
        user_id = str(uuid.UUID(str(payload.get("user_id"))))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Auth devolvio un identificador de usuario invalido.") from exc

    role = payload.get("role")
    if not isinstance(role, str) or role.strip().lower() not in ALLOWED_ROLES:
        raise HTTPException(status_code=503, detail="Auth devolvio un rol invalido.")

    session_version = payload.get("session_version")
    if (
        not isinstance(session_version, int)
        or isinstance(session_version, bool)
        or session_version < 1
    ):
        raise HTTPException(status_code=503, detail="Auth devolvio una version de sesion invalida.")

    return {
        **payload,
        "user_id": user_id,
        "role": role.strip().lower(),
        "session_version": session_version,
    }


def _active_payload(request: Request) -> dict:
    token = _extract_token(request)
    return introspect_token(token)


def _normalized_subject(payload: dict) -> str:
    try:
        return str(uuid.UUID(str(payload.get("sub") or payload.get("user_id") or payload.get("id"))))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Token invalido: subject no es UUID.") from exc


def get_current_user_id(request: Request) -> str:
    payload = _active_payload(request)
    if payload.get("type") not in (None, "access"):
        raise HTTPException(status_code=401, detail="Token de acceso invalido.")
    return _normalized_subject(payload)


def require_staff_or_superuser(request: Request) -> str:
    payload = _active_payload(request)
    if payload.get("role") not in ("staff", "superuser"):
        raise HTTPException(status_code=403, detail="Se requiere rol staff o superuser.")
    return _normalized_subject(payload)


def require_superuser(request: Request) -> str:
    payload = _active_payload(request)
    if payload.get("role") != "superuser":
        raise HTTPException(status_code=403, detail="Se requiere rol superuser.")
    return _normalized_subject(payload)


def require_internal_service(
    service_token: str | None = Header(default=None, alias="X-Internal-Service-Token"),
) -> str:
    expected = os.getenv("INTERNAL_SERVICE_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Autenticacion interna no configurada.")
    if not service_token or not secrets.compare_digest(service_token, expected):
        raise HTTPException(status_code=401, detail="Token interno invalido.")
    return "internal-service"
