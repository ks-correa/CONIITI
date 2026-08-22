from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class CommitteeMemberCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=255)
    cargo: str = Field(..., min_length=2, max_length=255)
    institucion: Optional[str] = Field(default=None, max_length=255)
    foto_url: Optional[str] = Field(default=None, max_length=1000)
    bio: Optional[str] = None
    orden: int = Field(default=0, ge=0)
    activo: bool = True

    @field_validator("nombre", "cargo", mode="before")
    @classmethod
    def clean_required(cls, value: str) -> str:
        if value is None:
            return value
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Este campo no puede estar vacio.")
        return cleaned

    @field_validator("institucion", "foto_url", "bio")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CommitteeMemberUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=255)
    cargo: Optional[str] = Field(default=None, min_length=2, max_length=255)
    institucion: Optional[str] = Field(default=None, max_length=255)
    foto_url: Optional[str] = Field(default=None, max_length=1000)
    bio: Optional[str] = None
    orden: Optional[int] = Field(default=None, ge=0)
    activo: Optional[bool] = None

    @field_validator("nombre", "cargo", mode="before")
    @classmethod
    def clean_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Este campo no puede estar vacio.")
        return cleaned

    @field_validator("institucion", "foto_url", "bio")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CommitteeMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nombre: str
    cargo: str
    institucion: Optional[str] = None
    foto_url: Optional[str] = None
    bio: Optional[str] = None
    orden: int
    activo: bool
    created_at: Optional[datetime] = None
