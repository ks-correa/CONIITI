import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_user import AuthUser

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(payload: dict) -> str:
    return create_signed_token(
        payload,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_signed_token(payload: dict, token_type: str, expires_delta: timedelta) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expires_delta.total_seconds()
    )
    token_payload = payload.copy()
    token_payload.update({"type": token_type, "exp": expires_at})
    return jwt.encode(
        token_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return decode_signed_token(token, expected_type="access")


def decode_signed_token(token: str, expected_type: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No fue posible validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise credentials_exception from exc

    if payload.get("type") != expected_type:
        raise credentials_exception

    return payload


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="session_hint",
        value="1",
        httponly=False,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="session_hint", path="/")


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def set_oauth_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.OAUTH_STATE_EXPIRE_MINUTES * 60,
        path="/",
    )


def clear_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(key="oauth_state", path="/")


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]

    token_from_cookie = request.cookies.get("access_token")
    if token_from_cookie:
        return token_from_cookie

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de acceso requerido.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthUser:
    token = _extract_bearer_token(request)
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()

    token_session_version = payload.get("sv")
    try:
        session_is_current = int(token_session_version) == user.session_version if user else False
    except (TypeError, ValueError):
        session_is_current = False

    if not user or not user.is_active or not session_is_current:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no valido o inactivo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
