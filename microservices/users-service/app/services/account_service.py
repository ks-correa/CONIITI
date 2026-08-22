import logging

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.clients import auth_client
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.user_schema import (
    AdminProfileUpdateRequest,
    ProfileUpdateRequest,
    SelfProfileUpdateRequest,
)
from app.services import profile_service
from app.utils.security import AuthenticatedUser


logger = logging.getLogger(__name__)


def _auth_error(exc: httpx.HTTPError, fallback: str) -> HTTPException:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            detail = exc.response.json().get("detail", fallback)
        except (ValueError, TypeError):
            detail = fallback
        return HTTPException(status_code=exc.response.status_code, detail=detail)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=fallback)


def _as_profile_update(payload) -> ProfileUpdateRequest:
    return ProfileUpdateRequest.model_validate(payload.model_dump(exclude_unset=True))


def update_own_profile(
    current_user: AuthenticatedUser,
    payload: SelfProfileUpdateRequest,
    db: Session,
) -> User:
    user = profile_service.get_user_or_404(current_user.id, db)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="La cuenta esta inactiva.")

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("full_name", object()) is None:
        changes.pop("full_name", None)
    prospective_first = changes.get("first_name", user.first_name)
    prospective_last = changes.get("last_name", user.last_name)
    prospective_name = changes.get("full_name")
    if not prospective_name and ("first_name" in changes or "last_name" in changes):
        prospective_name = " ".join(part for part in (prospective_first, prospective_last) if part)

    old_name = user.full_name
    auth_name_changed = bool(prospective_name and prospective_name != old_name)
    if auth_name_changed:
        try:
            auth_client.update_auth_account(user.id, {"full_name": prospective_name})
        except httpx.HTTPError as exc:
            raise _auth_error(exc, "No fue posible sincronizar el nombre con auth-service.") from exc

    try:
        return profile_service.update_profile_record(user, _as_profile_update(payload), db)
    except Exception:
        db.rollback()
        if auth_name_changed:
            try:
                auth_client.update_auth_account(user.id, {"full_name": old_name})
            except httpx.HTTPError:
                logger.exception("No se pudo compensar el nombre en auth-service para %s", user.id)
        raise


def _ensure_superuser_continuity(user: User, changes: dict, db: Session) -> None:
    current_role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    next_role = changes.get("role", current_role)
    next_active = changes.get("is_active", user.is_active)
    removes_active_superuser = (
        current_role == UserRole.SUPERUSER.value
        and user.is_active
        and (next_role != UserRole.SUPERUSER.value or not next_active)
    )
    if not removes_active_superuser:
        return

    active_superusers = (
        db.query(User)
        .filter(
            func.lower(User.role) == UserRole.SUPERUSER.value,
            User.is_active.is_(True),
        )
        .with_for_update()
        .all()
    )
    if len(active_superusers) <= 1:
        raise HTTPException(
            status_code=409,
            detail="Debe permanecer al menos un superusuario activo.",
        )


def update_profile_as_superuser(
    actor: AuthenticatedUser,
    user_id: str,
    payload: AdminProfileUpdateRequest,
    db: Session,
) -> User:
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    changes = payload.model_dump(exclude_unset=True)
    for required_field in ("full_name", "role", "is_active"):
        if changes.get(required_field, object()) is None:
            changes.pop(required_field, None)
    if actor.id == user.id and (
        ("role" in changes and changes["role"] != actor.role)
        or changes.get("is_active") is False
    ):
        raise HTTPException(
            status_code=409,
            detail="No puedes cambiar tu propio rol ni desactivar tu propia cuenta.",
        )
    _ensure_superuser_continuity(user, changes, db)

    old_name = user.full_name
    old_active = user.is_active
    new_role = changes.get("role")
    role_changed = new_role is not None and new_role != (
        user.role.value if isinstance(user.role, UserRole) else str(user.role)
    )
    active_changed = "is_active" in changes and changes["is_active"] != user.is_active
    prospective_first = changes.get("first_name", user.first_name)
    prospective_last = changes.get("last_name", user.last_name)
    prospective_name = changes.get("full_name")
    if not prospective_name and ("first_name" in changes or "last_name" in changes):
        prospective_name = " ".join(part for part in (prospective_first, prospective_last) if part)
    name_changed = bool(prospective_name and prospective_name != old_name)

    desired_active = changes.get("is_active", user.is_active)
    security_fields_requested = actor.id != user.id and (
        "role" in changes or "is_active" in changes
    )
    security_change = role_changed or active_changed or security_fields_requested
    suspended_before_update = (
        role_changed
        or (actor.id != user.id and "role" in changes)
        or ((active_changed or security_fields_requested) and not desired_active)
    )
    if suspended_before_update:
        try:
            # Close the login race before changing the role owner. While this
            # saga runs, Auth cannot issue a token carrying the previous role.
            auth_client.revoke_auth_sessions(user.id, is_active=False)
        except httpx.HTTPError as exc:
            db.rollback()
            raise _auth_error(exc, "No fue posible suspender la sesion antes del cambio.") from exc

    try:
        updated = profile_service.update_profile_record(user, _as_profile_update(payload), db)
    except Exception:
        db.rollback()
        try:
            if suspended_before_update:
                auth_client.revoke_auth_sessions(user.id, is_active=old_active)
        except httpx.HTTPError:
            logger.exception("Compensacion de estado Users/Auth fallida para %s", user.id)
        raise

    # Promotions/demotions and activations finish by issuing a fresh version
    # while re-enabling only the state already committed in Users.
    if security_change and desired_active:
        try:
            auth_client.revoke_auth_sessions(user.id, is_active=True)
        except httpx.HTTPError as exc:
            # If this fails after Users commits, Auth remains inactive (the
            # restrictive side). Repeating the desired patch retries safely.
            logger.exception("Sincronizacion de seguridad Users/Auth fallida para %s", user.id)
            raise _auth_error(
                exc,
                "El perfil se guardo, pero la cuenta quedo suspendida hasta completar la sincronizacion.",
            ) from exc

    if name_changed:
        try:
            auth_client.update_auth_account(user.id, {"full_name": prospective_name})
        except httpx.HTTPError:
            # Users owns profile data and /auth/me reads it from Users. A stale
            # display name in Auth is non-privileged and must not roll back a
            # successful profile update.
            logger.exception("Sincronizacion de nombre Users/Auth pendiente para %s", user.id)

    return updated
