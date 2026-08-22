import os
import uuid
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt


PAYMENT_MANAGER_ROLES = {"staff", "superuser"}
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")

if not AUTH_SERVICE_URL and not SECRET_KEY:
    raise ValueError("Missing JWT_SECRET_KEY (or SECRET_KEY) environment variable.")


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    role: str
    email: str | None = None
    full_name: str | None = None

    @property
    def can_manage_payments(self) -> bool:
        return self.role in PAYMENT_MANAGER_ROLES


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
    introspected = bool(AUTH_SERVICE_URL)
    if introspected:
        if not INTERNAL_SERVICE_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="La validacion de sesiones no esta configurada.",
            )
        try:
            response = httpx.post(
                f"{AUTH_SERVICE_URL.rstrip('/')}/internal/introspect",
                headers={"X-Internal-Service-Token": INTERNAL_SERVICE_TOKEN},
                json={"token": token},
                timeout=3,
            )
            response.raise_for_status()
            introspection = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo validar la sesion.",
            ) from exc
        if not isinstance(introspection, dict):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth devolvio un contrato de introspeccion invalido.",
            )
        if introspection.get("active") is not True:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesion invalida, expirada o revocada.",
            )
        payload = {
            "sub": introspection.get("user_id"),
            "role": introspection.get("role"),
            "email": introspection.get("email"),
            "full_name": introspection.get("full_name"),
            "type": "access",
        }
    else:
        # Compatibility for isolated unit tests. Every deployed manifest sets
        # AUTH_SERVICE_URL and therefore uses revocation-aware introspection.
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    if not user_id or not isinstance(role, str) or not role.strip():
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
                if introspected
                else status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Auth devolvio metadatos de sesion invalidos."
                if introspected
                else "Token incompleto."
            ),
        )

    try:
        normalized_user_id = str(uuid.UUID(str(user_id)))
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
                if introspected
                else status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Auth devolvio un subject invalido."
                if introspected
                else "Token invalido: subject no es UUID."
            ),
        ) from exc

    return AuthenticatedUser(
        id=normalized_user_id,
        role=role.strip().lower(),
        email=payload.get("email"),
        full_name=payload.get("full_name"),
    )


def require_payment_access(user_id: uuid.UUID, current_user: AuthenticatedUser) -> None:
    if current_user.can_manage_payments:
        return

    if str(user_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes operar pagos de otro usuario.",
        )
