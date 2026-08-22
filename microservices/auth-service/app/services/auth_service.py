import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.otp_code import OTPCode
from app.models.auth_user import AuthUser
from app.models.password_reset_token import PasswordResetToken
from app.schemas.auth import (
    InternalUserCreateRequest,
    InternalUserUpdateRequest,
    RegisterRequest,
)
from app.utils.jwt import create_access_token, decode_access_token, hash_password, verify_password


def get_user_by_email(email: str, db: Session) -> AuthUser | None:
    return db.query(AuthUser).filter(AuthUser.email == email).first()


def get_user_by_id(user_id: str, db: Session) -> Optional[AuthUser]:
    return db.query(AuthUser).filter(AuthUser.id == user_id).first()


def register_user(payload: RegisterRequest, db: Session) -> AuthUser:
    existing_user = get_user_by_email(payload.email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta registrada con ese correo.",
        )

    user = AuthUser(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(email: str, password: str, db: Session) -> AuthUser:
    user = get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe una cuenta registrada con ese correo.",
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contrasena es incorrecta.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva.",
        )
    return user


def create_access_token_for_user(
    user: AuthUser,
    role: str,
    full_name: str,
) -> str:
    return create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "full_name": full_name,
            "role": role,
            "sv": user.session_version,
        }
    )


def create_oauth_user(email: str, full_name: str, db: Session) -> AuthUser:
    user = AuthUser(
        email=email,
        full_name=full_name or email.split("@", 1)[0],
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_oauth_user(email: str, full_name: str, db: Session) -> tuple[AuthUser, bool]:
    existing_user = get_user_by_email(email, db)
    if existing_user:
        return existing_user, False
    return create_oauth_user(email=email, full_name=full_name, db=db), True


def delete_user(user: AuthUser, db: Session) -> None:
    db.query(OTPCode).filter(OTPCode.user_id == user.id).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete(
        synchronize_session=False
    )
    db.delete(user)
    db.commit()


def create_internal_user(payload: InternalUserCreateRequest, db: Session) -> AuthUser:
    if get_user_by_email(payload.email, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta registrada con ese correo.",
        )

    user = AuthUser(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
        is_verified=True,
    )
    if payload.user_id:
        user.id = payload.user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_internal_user(user_id: str, payload: InternalUserUpdateRequest, db: Session) -> AuthUser:
    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    must_revoke = False

    if payload.email and payload.email != user.email:
        existing = get_user_by_email(payload.email, db)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una cuenta registrada con ese correo.",
            )
        user.email = payload.email
        must_revoke = True

    if payload.full_name:
        user.full_name = payload.full_name

    if payload.password:
        user.password_hash = hash_password(payload.password)
        must_revoke = True

    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        must_revoke = True

    if must_revoke:
        user.session_version += 1

    db.commit()
    db.refresh(user)
    return user


def delete_user_by_id(user_id: str, db: Session) -> None:
    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    db.delete(user)
    db.commit()


def mark_user_verified(user: AuthUser, db: Session) -> AuthUser:
    if user.is_verified:
        return user

    user.is_verified = True
    db.commit()
    db.refresh(user)
    return user


def requires_login_otp(user: AuthUser, role: str) -> bool:
    normalized_role = role.strip().lower()
    return (not user.is_verified) or normalized_role in {"staff", "superuser"}


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_token(user: AuthUser, db: Session) -> str:
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update({"used": True}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.RESET_PASSWORD_TOKEN_EXPIRE_MINUTES),
    )
    db.add(token)
    db.commit()
    return raw_token


def reset_password(token: str, new_password: str, db: Session) -> AuthUser:
    token_hash = _hash_reset_token(token)
    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used.is_(False),
        )
        .first()
    )

    now = datetime.now(timezone.utc)
    expires_at = reset_token.expires_at if reset_token else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not reset_token or expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento es invalido o ya expiro.",
        )

    user = get_user_by_id(reset_token.user_id, db)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo restablecer la contrasena para esta cuenta.",
        )

    user.password_hash = hash_password(new_password)
    user.session_version += 1
    reset_token.used = True
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update({"used": True}, synchronize_session=False)
    db.commit()
    db.refresh(user)
    return user


def revoke_sessions(
    user_id: str,
    db: Session,
    *,
    is_active: bool | None = None,
) -> AuthUser:
    """Invalidate every access token issued before this transaction."""
    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    if is_active is not None:
        user.is_active = is_active
    user.session_version += 1
    db.commit()
    db.refresh(user)
    return user


def introspect_access_token(token: str, db: Session) -> dict:
    """Validate signature, expiry, account state and session version.

    Role ownership remains in users-service.  Auth only returns the role claim
    after proving that the claim belongs to the latest valid session version.
    """
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return {"active": False}

    user_id = payload.get("sub")
    token_version = payload.get("sv")
    role = payload.get("role")
    if not user_id or token_version is None or not role:
        return {"active": False}

    user = get_user_by_id(str(user_id), db)
    if not user or not user.is_active:
        return {"active": False}

    try:
        version_matches = int(token_version) == user.session_version
    except (TypeError, ValueError):
        version_matches = False
    if not version_matches:
        return {"active": False}

    return {
        "active": True,
        "user_id": user.id,
        "email": user.email,
        "full_name": payload.get("full_name") or user.full_name,
        "role": role,
        "session_version": user.session_version,
        "expires_at": payload.get("exp"),
    }
