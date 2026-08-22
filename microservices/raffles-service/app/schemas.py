from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


RaffleStatus = Literal["draft", "eligibility_locked", "drawn", "published", "cancelled"]


class RaffleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    eligibility_rule: dict[str, Any] = Field(default_factory=dict)
    winner_count: int = Field(default=1, ge=1, le=100)
    closes_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())


class RaffleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    status: RaffleStatus
    eligibility_rule: dict[str, Any]
    winner_count: int
    closes_at: datetime | None
    snapshot_at: datetime | None
    snapshot_hash: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    eligible_count: int = 0
    drawn_count: int = 0


class SnapshotRead(BaseModel):
    raffle_id: str
    status: RaffleStatus
    eligible_count: int
    snapshot_at: datetime
    snapshot_hash: str


class EligibilityItem(BaseModel):
    user_id: str
    ordinal: int
    attendance_evidence: dict[str, Any]
    full_name: str | None = None


class EligibilityPage(BaseModel):
    items: list[EligibilityItem]
    total: int
    page: int
    page_size: int


class WinnerRead(BaseModel):
    user_id: str
    full_name: str | None = None
    draw_number: int
    drawn_at: datetime
    algorithm_version: str
    snapshot_hash: str
    random_evidence: str
    audit_hash: str


class PublishRead(BaseModel):
    raffle_id: str
    status: RaffleStatus
    published_at: datetime


class PublicWinner(BaseModel):
    draw_number: int
    drawn_at: datetime
    winner_reference: str


class RaffleResult(BaseModel):
    raffle_id: str
    name: str
    status: RaffleStatus
    published_at: datetime | None
    winners: list[PublicWinner | WinnerRead]
