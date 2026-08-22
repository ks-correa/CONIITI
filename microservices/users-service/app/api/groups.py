from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.group_schema import (
    GroupAuditResponse,
    GroupCreateRequest,
    GroupMemberCreateRequest,
    GroupMemberResponse,
    GroupMemberUpdateRequest,
    GroupResponse,
    GroupUpdateRequest,
    PaginatedGroupsResponse,
)
from app.services import group_service
from app.utils.security import AuthenticatedUser, get_current_user, require_superuser


router = APIRouter(prefix="/groups", tags=["Groups"])
me_router = APIRouter(tags=["Groups"])


@router.get("", response_model=PaginatedGroupsResponse)
def list_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=160),
    db: Session = Depends(get_db),
    _: Any = Depends(require_superuser),
):
    return group_service.list_groups(page, page_size, search, db)


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreateRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_superuser),
):
    return group_service.create_group(payload, actor, db)


@me_router.get("/me/groups", response_model=list[GroupResponse])
def list_my_groups(
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.list_my_groups(actor, db)


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.get_group(group_id, actor, db)


@router.patch("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: str,
    payload: GroupUpdateRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.update_group(group_id, payload, actor, db)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_superuser),
):
    group_service.deactivate_group(group_id, actor, db)


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
def list_group_members(
    group_id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.list_members(group_id, actor, db)


@router.post(
    "/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_group_member(
    group_id: str,
    payload: GroupMemberCreateRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.add_member(group_id, payload, actor, db)


@router.patch("/{group_id}/members/{user_id}", response_model=GroupMemberResponse)
def update_group_member(
    group_id: str,
    user_id: str,
    payload: GroupMemberUpdateRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.update_member(group_id, user_id, payload, actor, db)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_group_member(
    group_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    group_service.remove_member(group_id, user_id, actor, db)


@router.get("/{group_id}/audit", response_model=list[GroupAuditResponse])
def list_group_audit(
    group_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(get_current_user),
):
    return group_service.list_audit(group_id, actor, db, limit)
