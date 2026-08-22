import math
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.roles import UserRole
from app.models.user import User
from app.schemas.user_schema import ProfileCreateRequest, ProfileUpdateRequest


PROFILE_FIELDS = (
    "first_name",
    "last_name",
    "institution",
    "career",
    "gender",
    "document",
    "institutional_code",
)


def get_user_or_404(user_id: str, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


def _check_unique_profile_identifiers(
    db: Session,
    *,
    document: str | None,
    institutional_code: str | None,
    exclude_user_id: str | None = None,
) -> None:
    for column, value, label in (
        (User.document, document, "documento"),
        (User.institutional_code, institutional_code, "codigo institucional"),
    ):
        if not value:
            continue
        query = db.query(User.id).filter(func.lower(column) == value.lower())
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"Ya existe un perfil con ese {label}.")


def _update_completion_state(user: User) -> None:
    completed = bool(user.first_name and user.last_name)
    if completed and user.profile_completed_at is None:
        user.profile_completed_at = datetime.now(timezone.utc)
    elif not completed:
        user.profile_completed_at = None


def create_profile_record(profile: ProfileCreateRequest, db: Session) -> User:
    normalized_email = str(profile.email).strip().lower()
    if db.query(User.id).filter(func.lower(User.email) == normalized_email).first():
        raise HTTPException(status_code=409, detail="Ya existe un perfil con ese correo.")

    if profile.id and db.query(User.id).filter(User.id == profile.id).first():
        raise HTTPException(status_code=409, detail="Ya existe un perfil con ese identificador.")

    normalized_document = profile.document.upper() if profile.document else None
    normalized_code = profile.institutional_code.upper() if profile.institutional_code else None
    _check_unique_profile_identifiers(
        db,
        document=normalized_document,
        institutional_code=normalized_code,
    )
    user_data = profile.model_dump(exclude={"id"})
    user_data["email"] = normalized_email
    user_data["document"] = normalized_document
    user_data["institutional_code"] = normalized_code
    if profile.id:
        user_data["id"] = profile.id

    new_user = User(**user_data)
    _update_completion_state(new_user)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def list_profiles(db: Session, role: str | None = None) -> list[User]:
    query = db.query(User)
    if role:
        query = query.filter(func.lower(User.role) == role.strip().lower())
    return query.order_by(User.created_at.desc()).all()


def list_profiles_paginated(
    db: Session,
    *,
    search: str | None,
    role: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> dict:
    query = db.query(User)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.full_name).like(term),
                func.lower(User.email).like(term),
                func.lower(func.coalesce(User.document, "")).like(term),
                func.lower(func.coalesce(User.institutional_code, "")).like(term),
            )
        )
    if role:
        normalized_role = role.strip().lower()
        if normalized_role not in {item.value for item in UserRole}:
            raise HTTPException(status_code=422, detail="Filtro de rol invalido.")
        query = query.filter(func.lower(User.role) == normalized_role)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    total = query.count()
    items = (
        query.order_by(User.created_at.desc(), User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


def get_profile_by_email(email: str, db: Session) -> User:
    user = db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


def update_profile_record(user: User, profile_update: ProfileUpdateRequest, db: Session) -> User:
    changes = profile_update.model_dump(exclude_unset=True)
    for required_field in ("full_name", "email", "role", "is_active"):
        if changes.get(required_field, object()) is None:
            changes.pop(required_field, None)
    if changes.get("document"):
        changes["document"] = changes["document"].upper()
    if changes.get("institutional_code"):
        changes["institutional_code"] = changes["institutional_code"].upper()
    if "email" in changes and changes["email"] is not None:
        normalized_email = str(changes["email"]).strip().lower()
        existing = db.query(User.id).filter(
            func.lower(User.email) == normalized_email,
            User.id != user.id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Ya existe un perfil con ese correo.")
        changes["email"] = normalized_email

    _check_unique_profile_identifiers(
        db,
        document=changes.get("document", user.document),
        institutional_code=changes.get("institutional_code", user.institutional_code),
        exclude_user_id=user.id,
    )

    for field, value in changes.items():
        setattr(user, field, value)

    if ("first_name" in changes or "last_name" in changes) and "full_name" not in changes:
        joined_name = " ".join(part for part in (user.first_name, user.last_name) if part)
        if joined_name:
            user.full_name = joined_name
    _update_completion_state(user)

    db.commit()
    db.refresh(user)
    return user


def delete_profile_record(user: User, db: Session) -> None:
    db.delete(user)
    db.commit()


def list_staff_profiles(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(func.lower(User.role) == UserRole.STAFF.value)
        .order_by(User.created_at.desc())
        .all()
    )


def get_profile_summaries(user_ids: list[str], db: Session) -> dict:
    users = db.query(User.id, User.full_name).filter(User.id.in_(user_ids)).all()
    by_id = {user.id: user.full_name for user in users}
    return {
        "items": [{"id": user_id, "full_name": by_id[user_id]} for user_id in user_ids if user_id in by_id],
        "missing_ids": [user_id for user_id in user_ids if user_id not in by_id],
    }
