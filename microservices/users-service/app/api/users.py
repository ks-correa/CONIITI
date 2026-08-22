from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user_schema import (
    AdminProfileUpdateRequest,
    PaginatedProfilesResponse,
    ProfileCreateRequest,
    ProfileResponse,
    ProfileSummaryRequest,
    ProfileSummaryResponse,
    ProfileUpdateRequest,
    SelfProfileUpdateRequest,
    StaffCreateRequest,
    StaffUpdateRequest,
)
from app.utils.security import AuthenticatedUser, get_current_user, require_internal_request, require_superuser
from app.services import account_service, profile_service, staff_service


router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    return profile_service.get_user_or_404(current_user.id, db)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: SelfProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    return account_service.update_own_profile(current_user, payload, db)


@router.get("/admin/profiles", response_model=PaginatedProfilesResponse)
def list_profiles_for_admin(
    search: str | None = Query(default=None, max_length=255),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Any = Depends(require_superuser),
):
    return profile_service.list_profiles_paginated(
        db,
        search=search,
        role=role,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.patch("/admin/profiles/{user_id}", response_model=ProfileResponse)
def update_profile_for_admin(
    user_id: str,
    payload: AdminProfileUpdateRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_superuser),
):
    return account_service.update_profile_as_superuser(actor, user_id, payload, db)


@router.post("/internal/profile-summaries", response_model=ProfileSummaryResponse)
def get_internal_profile_summaries(
    payload: ProfileSummaryRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.get_profile_summaries(payload.user_ids, db)


@router.post("/internal/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    user: ProfileCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.create_profile_record(user, db)


@router.get("/internal/profiles")
def get_profiles(
    role: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.list_profiles(db, role=role)


@router.get("/internal/profiles/by-email", response_model=ProfileResponse)
def get_profile_by_email(
    email: str = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.get_profile_by_email(email, db)


@router.get("/internal/profiles/{user_id}", response_model=ProfileResponse)
def get_profile(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.get_user_or_404(user_id, db)


@router.patch("/internal/profiles/{user_id}", response_model=ProfileResponse)
def update_profile(
    user_id: str,
    user_data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = profile_service.get_user_or_404(user_id, db)
    return profile_service.update_profile_record(user, user_data, db)


@router.delete("/internal/profiles/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = profile_service.get_user_or_404(user_id, db)
    profile_service.delete_profile_record(user, db)


# Compatibilidad temporal para clientes internos legacy.
@router.post("/users/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile_legacy(
    user: ProfileCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.create_profile_record(user, db)


@router.get("/users/")
def get_profiles_legacy(
    role: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.list_profiles(db, role=role)


@router.get("/users/{user_id}", response_model=ProfileResponse)
def get_profile_legacy(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return profile_service.get_user_or_404(user_id, db)


@router.put("/users/{user_id}", response_model=ProfileResponse)
@router.patch("/users/{user_id}", response_model=ProfileResponse)
def update_profile_legacy(
    user_id: str,
    user_data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = profile_service.get_user_or_404(user_id, db)
    return profile_service.update_profile_record(user, user_data, db)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile_legacy(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = profile_service.get_user_or_404(user_id, db)
    profile_service.delete_profile_record(user, db)


@router.get("/staff", response_model=list[ProfileResponse])
def list_staff(
    db: Session = Depends(get_db),
    _: Any = Depends(require_superuser),
):
    return profile_service.list_staff_profiles(db)


@router.post("/staff", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    user: StaffCreateRequest,
    db: Session = Depends(get_db),
    _: Any = Depends(require_superuser),
):
    return staff_service.create_staff_account(user, db)


@router.put("/staff/{user_id}", response_model=ProfileResponse)
@router.patch("/staff/{user_id}", response_model=ProfileResponse)
def update_staff(
    user_id: str,
    user_data: StaffUpdateRequest,
    db: Session = Depends(get_db),
    _: Any = Depends(require_superuser),
):
    return staff_service.update_staff_account(user_id, user_data, db)


@router.delete("/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff(
    user_id: str,
    db: Session = Depends(get_db),
    _: Any = Depends(require_superuser),
):
    staff_service.delete_staff_account(user_id, db)
