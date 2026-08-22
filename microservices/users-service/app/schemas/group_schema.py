from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.group import GroupMembershipRole


def _clean_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Este campo no puede estar vacio.")
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class GroupUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _clean_required(value) if value is not None else None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class GroupMemberCreateRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    email: Optional[EmailStr] = None
    membership_role: GroupMembershipRole = GroupMembershipRole.MEMBER

    @field_validator("user_id")
    @classmethod
    def clean_user_id(cls, value: str | None) -> str | None:
        return _clean_required(value) if value is not None else None

    @model_validator(mode="after")
    def require_one_identifier(self):
        if bool(self.user_id) == bool(self.email):
            raise ValueError("Envia user_id o email, pero no ambos.")
        return self


class GroupMemberUpdateRequest(BaseModel):
    membership_role: Optional[GroupMembershipRole] = None
    is_active: Optional[bool] = None


class GroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    member_count: int = 0
    admin_count: int = 0
    current_membership_role: Optional[GroupMembershipRole] = None
    created_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedGroupsResponse(BaseModel):
    items: list[GroupResponse]
    total: int
    page: int
    page_size: int
    pages: int


class GroupMemberResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    membership_role: GroupMembershipRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GroupAuditResponse(BaseModel):
    id: str
    group_id: str
    actor_id: str
    action: str
    subject_user_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
