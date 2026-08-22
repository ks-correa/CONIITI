import math

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.group import Group, GroupMembership, GroupMembershipRole
from app.models.group_audit import GroupAuditLog
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.group_schema import (
    GroupCreateRequest,
    GroupMemberCreateRequest,
    GroupMemberUpdateRequest,
    GroupUpdateRequest,
)
from app.utils.security import AuthenticatedUser


def _global_role(actor: AuthenticatedUser) -> str:
    return actor.role.strip().lower()


def _is_superuser(actor: AuthenticatedUser) -> bool:
    return _global_role(actor) == UserRole.SUPERUSER.value


def _membership_role(membership: GroupMembership) -> str:
    value = membership.membership_role
    return value.value if isinstance(value, GroupMembershipRole) else str(value)


def get_group_or_404(group_id: str, db: Session) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo no encontrado.")
    return group


def get_membership(
    group_id: str,
    user_id: str,
    db: Session,
    *,
    active_only: bool = True,
) -> GroupMembership | None:
    query = db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == user_id,
    )
    if active_only:
        query = query.filter(GroupMembership.is_active.is_(True))
    return query.first()


def _require_member(group: Group, actor: AuthenticatedUser, db: Session) -> GroupMembership | None:
    if _is_superuser(actor):
        return get_membership(group.id, actor.id, db)
    if not group.is_active:
        raise HTTPException(status_code=404, detail="Grupo no encontrado.")
    membership = get_membership(group.id, actor.id, db)
    if not membership:
        raise HTTPException(status_code=403, detail="No perteneces a este grupo.")
    return membership


def _require_group_admin(group: Group, actor: AuthenticatedUser, db: Session) -> GroupMembership | None:
    if _is_superuser(actor):
        return get_membership(group.id, actor.id, db)
    membership = _require_member(group, actor, db)
    if not membership or _membership_role(membership) != GroupMembershipRole.GROUP_ADMIN.value:
        raise HTTPException(status_code=403, detail="Se requiere ser administrador de este grupo.")
    return membership


def _audit(
    db: Session,
    group_id: str,
    actor_id: str,
    action: str,
    *,
    subject_user_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        GroupAuditLog(
            group_id=group_id,
            actor_id=actor_id,
            action=action,
            subject_user_id=subject_user_id,
            details=metadata or {},
        )
    )


def _counts(group_id: str, db: Session) -> tuple[int, int]:
    memberships = db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.is_active.is_(True),
    )
    total = memberships.count()
    admins = memberships.filter(
        GroupMembership.membership_role == GroupMembershipRole.GROUP_ADMIN,
    ).count()
    return total, admins


def serialize_group(group: Group, db: Session, current_user_id: str | None = None) -> dict:
    member_count, admin_count = _counts(group.id, db)
    membership = get_membership(group.id, current_user_id, db) if current_user_id else None
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "is_active": group.is_active,
        "member_count": member_count,
        "admin_count": admin_count,
        "current_membership_role": membership.membership_role if membership else None,
        "created_by_id": group.created_by_id,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def create_group(payload: GroupCreateRequest, actor: AuthenticatedUser, db: Session) -> dict:
    if db.query(Group.id).filter(func.lower(Group.name) == payload.name.lower()).first():
        raise HTTPException(status_code=409, detail="Ya existe un grupo con ese nombre.")
    creator = db.query(User).filter(User.id == actor.id, User.is_active.is_(True)).first()
    if not creator:
        raise HTTPException(status_code=409, detail="El superusuario no tiene un perfil activo en users-service.")

    group = Group(name=payload.name, description=payload.description, created_by_id=actor.id)
    db.add(group)
    db.flush()
    db.add(
        GroupMembership(
            group_id=group.id,
            user_id=actor.id,
            membership_role=GroupMembershipRole.GROUP_ADMIN,
            added_by_id=actor.id,
        )
    )
    _audit(db, group.id, actor.id, "group.created", metadata={"name": group.name})
    db.commit()
    db.refresh(group)
    return serialize_group(group, db, actor.id)


def list_groups(page: int, page_size: int, search: str | None, db: Session) -> dict:
    query = db.query(Group)
    if search and search.strip():
        query = query.filter(func.lower(Group.name).like(f"%{search.strip().lower()}%"))
    total = query.count()
    groups = query.order_by(Group.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize_group(group, db) for group in groups],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


def list_my_groups(actor: AuthenticatedUser, db: Session) -> list[dict]:
    rows = (
        db.query(Group, GroupMembership)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .filter(
            GroupMembership.user_id == actor.id,
            GroupMembership.is_active.is_(True),
            Group.is_active.is_(True),
        )
        .order_by(Group.name.asc())
        .all()
    )
    return [serialize_group(group, db, actor.id) for group, _membership in rows]


def get_group(group_id: str, actor: AuthenticatedUser, db: Session) -> dict:
    group = get_group_or_404(group_id, db)
    _require_member(group, actor, db)
    return serialize_group(group, db, actor.id)


def update_group(
    group_id: str,
    payload: GroupUpdateRequest,
    actor: AuthenticatedUser,
    db: Session,
) -> dict:
    group = get_group_or_404(group_id, db)
    _require_group_admin(group, actor, db)
    changes = payload.model_dump(exclude_unset=True)
    if not _is_superuser(actor) and "is_active" in changes:
        raise HTTPException(status_code=403, detail="Solo un superusuario puede cambiar el estado del grupo.")
    if "name" in changes:
        duplicate = db.query(Group.id).filter(
            func.lower(Group.name) == changes["name"].lower(),
            Group.id != group.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Ya existe un grupo con ese nombre.")
    for field, value in changes.items():
        setattr(group, field, value)
    _audit(db, group.id, actor.id, "group.updated", metadata={"fields": sorted(changes)})
    db.commit()
    db.refresh(group)
    return serialize_group(group, db, actor.id)


def deactivate_group(group_id: str, actor: AuthenticatedUser, db: Session) -> None:
    group = get_group_or_404(group_id, db)
    group.is_active = False
    _audit(db, group.id, actor.id, "group.deactivated")
    db.commit()


def list_members(group_id: str, actor: AuthenticatedUser, db: Session) -> list[dict]:
    group = get_group_or_404(group_id, db)
    _require_group_admin(group, actor, db)
    rows = (
        db.query(GroupMembership, User)
        .join(User, User.id == GroupMembership.user_id)
        .filter(GroupMembership.group_id == group.id)
        .order_by(GroupMembership.is_active.desc(), User.full_name.asc())
        .all()
    )
    return [
        {
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "membership_role": membership.membership_role,
            "is_active": membership.is_active,
            "created_at": membership.created_at,
            "updated_at": membership.updated_at,
        }
        for membership, user in rows
    ]


def add_member(
    group_id: str,
    payload: GroupMemberCreateRequest,
    actor: AuthenticatedUser,
    db: Session,
) -> dict:
    group = get_group_or_404(group_id, db)
    _require_group_admin(group, actor, db)
    if not group.is_active:
        raise HTTPException(status_code=409, detail="El grupo esta inactivo.")
    if not _is_superuser(actor) and payload.membership_role == GroupMembershipRole.GROUP_ADMIN:
        raise HTTPException(status_code=403, detail="Solo un superusuario puede designar administradores de grupo.")
    user_query = db.query(User).filter(User.is_active.is_(True))
    if payload.user_id:
        user_query = user_query.filter(User.id == payload.user_id)
    else:
        user_query = user_query.filter(func.lower(User.email) == str(payload.email).lower())
    user = user_query.first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario activo no encontrado.")

    membership = get_membership(group.id, user.id, db, active_only=False)
    if membership and membership.is_active:
        raise HTTPException(status_code=409, detail="El usuario ya pertenece al grupo.")
    if membership:
        membership.is_active = True
        membership.membership_role = payload.membership_role
        membership.added_by_id = actor.id
    else:
        membership = GroupMembership(
            group_id=group.id,
            user_id=user.id,
            membership_role=payload.membership_role,
            added_by_id=actor.id,
        )
        db.add(membership)
    _audit(
        db,
        group.id,
        actor.id,
        "membership.added",
        subject_user_id=user.id,
        metadata={"membership_role": payload.membership_role.value},
    )
    db.commit()
    db.refresh(membership)
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "membership_role": membership.membership_role,
        "is_active": membership.is_active,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


def _ensure_another_admin(membership: GroupMembership, db: Session) -> None:
    if not membership.is_active or _membership_role(membership) != GroupMembershipRole.GROUP_ADMIN.value:
        return
    admins = (
        db.query(GroupMembership)
        .filter(
            GroupMembership.group_id == membership.group_id,
            GroupMembership.is_active.is_(True),
            GroupMembership.membership_role == GroupMembershipRole.GROUP_ADMIN,
        )
        .with_for_update()
        .all()
    )
    if len(admins) <= 1:
        raise HTTPException(status_code=409, detail="El grupo debe conservar al menos un administrador activo.")


def update_member(
    group_id: str,
    user_id: str,
    payload: GroupMemberUpdateRequest,
    actor: AuthenticatedUser,
    db: Session,
) -> dict:
    group = get_group_or_404(group_id, db)
    _require_group_admin(group, actor, db)
    membership = get_membership(group.id, user_id, db, active_only=False)
    if not membership:
        raise HTTPException(status_code=404, detail="Membresia no encontrada.")
    changes = payload.model_dump(exclude_unset=True)
    target_is_admin = _membership_role(membership) == GroupMembershipRole.GROUP_ADMIN.value
    if not _is_superuser(actor) and ("membership_role" in changes or target_is_admin):
        raise HTTPException(status_code=403, detail="Solo un superusuario puede administrar roles de grupo.")

    removes_admin = target_is_admin and (
        changes.get("membership_role") == GroupMembershipRole.MEMBER
        or changes.get("is_active") is False
    )
    if removes_admin:
        _ensure_another_admin(membership, db)
    for field, value in changes.items():
        setattr(membership, field, value)
    _audit(
        db,
        group.id,
        actor.id,
        "membership.updated",
        subject_user_id=user_id,
        metadata={
            key: value.value if isinstance(value, GroupMembershipRole) else value
            for key, value in changes.items()
        },
    )
    db.commit()
    db.refresh(membership)
    user = db.query(User).filter(User.id == user_id).one()
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "membership_role": membership.membership_role,
        "is_active": membership.is_active,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


def remove_member(group_id: str, user_id: str, actor: AuthenticatedUser, db: Session) -> None:
    group = get_group_or_404(group_id, db)
    _require_group_admin(group, actor, db)
    membership = get_membership(group.id, user_id, db, active_only=False)
    if not membership:
        raise HTTPException(status_code=404, detail="Membresia no encontrada.")
    target_is_admin = _membership_role(membership) == GroupMembershipRole.GROUP_ADMIN.value
    if not _is_superuser(actor) and target_is_admin:
        raise HTTPException(status_code=403, detail="Solo un superusuario puede retirar administradores de grupo.")
    _ensure_another_admin(membership, db)
    membership.is_active = False
    _audit(db, group.id, actor.id, "membership.removed", subject_user_id=user_id)
    db.commit()


def list_audit(group_id: str, actor: AuthenticatedUser, db: Session, limit: int) -> list[dict]:
    group = get_group_or_404(group_id, db)
    _require_group_admin(group, actor, db)
    logs = (
        db.query(GroupAuditLog)
        .filter(GroupAuditLog.group_id == group.id)
        .order_by(GroupAuditLog.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "group_id": log.group_id,
            "actor_id": log.actor_id,
            "action": log.action,
            "subject_user_id": log.subject_user_id,
            "metadata": log.details,
            "occurred_at": log.occurred_at,
        }
        for log in logs
    ]
