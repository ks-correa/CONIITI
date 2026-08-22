import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.agenda import AttendanceMethod


class AttendanceTokenCreate(BaseModel):
    ttl_seconds: int = Field(default=120, ge=30, le=600)
    max_uses: int = Field(default=1, ge=1, le=5000)


class AttendanceTokenRead(BaseModel):
    token: str
    session_id: uuid.UUID
    expires_at: datetime
    max_uses: int


class AttendanceCheckIn(BaseModel):
    token: str = Field(min_length=20, max_length=5000)


class ManualAttendanceCreate(BaseModel):
    user_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)


class AttendanceRevoke(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AttendanceRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    confirmed_at: datetime
    confirmed_by: uuid.UUID
    method: AttendanceMethod
    confirmation_note: str | None = None
    verification_token_id: uuid.UUID | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    model_config = ConfigDict(from_attributes=True)


class AttendanceListResponse(BaseModel):
    total: int
    items: list[AttendanceRead]


class EligibilitySnapshotRequest(BaseModel):
    session_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    confirmed_from: datetime | None = None
    confirmed_to: datetime | None = None
    require_registration: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        if self.confirmed_from and self.confirmed_to and self.confirmed_from > self.confirmed_to:
            raise ValueError("confirmed_from debe ser anterior o igual a confirmed_to.")
        return self


class EligibilityItem(BaseModel):
    user_id: uuid.UUID
    session_id: uuid.UUID
    attendance_id: uuid.UUID
    confirmed_at: datetime


class EligibilitySnapshotResponse(BaseModel):
    items: list[EligibilityItem]
    total: int
