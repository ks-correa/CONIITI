from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.roles import UserRole


PROFILE_OPTIONAL_FIELDS = (
    "first_name",
    "last_name",
    "institution",
    "career",
    "gender",
    "document",
    "institutional_code",
)


def _normalize_role(value: str | None) -> str | None:
    if value is None:
        return value
    normalized = value.strip().lower()
    if normalized not in [role.value for role in UserRole]:
        raise ValueError(f"El rol debe ser uno de: {[role.value for role in UserRole]}")
    return normalized


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class ProfileFieldsMixin(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=120)
    last_name: Optional[str] = Field(default=None, max_length=120)
    institution: Optional[str] = Field(default=None, max_length=255)
    career: Optional[str] = Field(default=None, max_length=255)
    gender: Optional[str] = Field(default=None, max_length=80)
    document: Optional[str] = Field(default=None, max_length=100)
    institutional_code: Optional[str] = Field(default=None, max_length=100)

    @field_validator(*PROFILE_OPTIONAL_FIELDS, mode="before", check_fields=False)
    @classmethod
    def clean_optional_profile_field(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class ProfileCreateRequest(ProfileFieldsMixin):
    id: Optional[str] = None
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    role: str
    is_active: bool = True

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return _normalize_role(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class ProfileUpdateRequest(ProfileFieldsMixin):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str | None) -> str | None:
        return _normalize_role(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_full_name(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class SelfProfileUpdateRequest(ProfileFieldsMixin):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_full_name(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class AdminProfileUpdateRequest(ProfileFieldsMixin):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str | None) -> str | None:
        return _normalize_role(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_full_name(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class StaffCreateRequest(ProfileCreateRequest):
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class StaffUpdateRequest(ProfileUpdateRequest):
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    role: str
    institution: Optional[str] = None
    career: Optional[str] = None
    gender: Optional[str] = None
    document: Optional[str] = None
    institutional_code: Optional[str] = None
    is_active: bool
    profile_completed: bool = False
    profile_completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return _normalize_role(value)

class PaginatedProfilesResponse(BaseModel):
    items: list[ProfileResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ProfileSummaryRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=200)

    @field_validator("user_ids")
    @classmethod
    def unique_user_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            raise ValueError("Se requiere al menos un user_id.")
        if len(cleaned) > 200:
            raise ValueError("El limite es 200 usuarios por solicitud.")
        return list(dict.fromkeys(cleaned))


class ProfileSummaryItem(BaseModel):
    id: str
    full_name: str


class ProfileSummaryResponse(BaseModel):
    items: list[ProfileSummaryItem]
    missing_ids: list[str]


# Compatibilidad temporal con nombres anteriores.
UserCreate = StaffCreateRequest
UserUpdate = StaffUpdateRequest
UserResponse = ProfileResponse
