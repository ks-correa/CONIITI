import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models.agenda import ResourceState, ResourceType


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _http_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith("/") and not cleaned.startswith("//"):
        return cleaned
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL debe usar http o https.")
    return cleaned


class VenueBase(BaseModel):
    name: NonBlank = Field(max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    capacity: int = Field(ge=1, le=100_000)
    is_active: bool = True

    @field_validator("description", mode="before")
    @classmethod
    def clean_description(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: NonBlank | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    is_active: bool | None = None

    @field_validator("description", mode="before")
    @classmethod
    def clean_description(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class VenueResourceBase(BaseModel):
    resource_type: ResourceType
    title: NonBlank = Field(max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    alt_text: str | None = Field(default=None, max_length=500)
    asset_id: uuid.UUID | None = None
    external_url: str | None = Field(default=None, max_length=2000)
    mime_type: str | None = Field(default=None, max_length=255)
    captions_asset_id: uuid.UUID | None = None
    captions_url: str | None = Field(default=None, max_length=2000)
    transcript_asset_id: uuid.UUID | None = None
    transcript_url: str | None = Field(default=None, max_length=2000)
    display_order: int = Field(default=0, ge=0, le=10_000)
    is_active: bool = True

    @field_validator("external_url", "captions_url", "transcript_url", mode="before")
    @classmethod
    def validate_urls(cls, value):
        return _http_url(value)

    @field_validator("description", "alt_text", "mime_type", mode="before")
    @classmethod
    def clean_optional(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_source_and_accessibility(self):
        if bool(self.asset_id) == bool(self.external_url):
            raise ValueError("Indica exactamente asset_id o external_url.")
        if self.captions_asset_id and self.captions_url:
            raise ValueError("Indica captions_asset_id o captions_url, no ambos.")
        if self.transcript_asset_id and self.transcript_url:
            raise ValueError("Indica transcript_asset_id o transcript_url, no ambos.")
        if self.resource_type != ResourceType.VIDEO and any((
            self.captions_asset_id,
            self.captions_url,
            self.transcript_asset_id,
            self.transcript_url,
        )):
            raise ValueError("Los subtítulos y la transcripción solo aplican a recursos de video.")
        if self.resource_type in {ResourceType.VIDEO, ResourceType.IMAGE, ResourceType.POSTER} and not self.alt_text:
            raise ValueError("Los recursos visuales requieren texto alternativo.")
        return self


class VenueResourceCreate(VenueResourceBase):
    pass


class VenueResourceUpdate(BaseModel):
    resource_type: ResourceType | None = None
    title: NonBlank | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    alt_text: str | None = Field(default=None, max_length=500)
    asset_id: uuid.UUID | None = None
    external_url: str | None = Field(default=None, max_length=2000)
    mime_type: str | None = Field(default=None, max_length=255)
    captions_asset_id: uuid.UUID | None = None
    captions_url: str | None = Field(default=None, max_length=2000)
    transcript_asset_id: uuid.UUID | None = None
    transcript_url: str | None = Field(default=None, max_length=2000)
    display_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None

    @field_validator("external_url", "captions_url", "transcript_url", mode="before")
    @classmethod
    def validate_urls(cls, value):
        return _http_url(value)


class VenueResourceRead(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    resource_type: ResourceType
    title: str
    description: str | None = None
    alt_text: str | None = None
    asset_id: uuid.UUID | None = None
    url: str | None = None
    mime_type: str | None = None
    captions_asset_id: uuid.UUID | None = None
    captions_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("effective_captions_url", "captions_url"),
    )
    captions_resolved_url: str | None = None
    transcript_asset_id: uuid.UUID | None = None
    transcript_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("effective_transcript_url", "transcript_url"),
    )
    transcript_resolved_url: str | None = None
    display_order: int
    is_active: bool
    state: ResourceState
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VenueSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    capacity: int
    is_active: bool
    resources: list[VenueResourceRead] = Field(
        default_factory=list,
        validation_alias=AliasChoices("active_resources", "resources"),
    )
    model_config = ConfigDict(from_attributes=True)


class VenueRead(VenueSummary):
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class VenueListResponse(BaseModel):
    total: int
    venues: list[VenueRead]


class VenueAdminRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    capacity: int
    is_active: bool
    resources: list[VenueResourceRead] = Field(default_factory=list)
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VenueAdminListResponse(BaseModel):
    total: int
    venues: list[VenueAdminRead]
