import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Raffle(Base):
    __tablename__ = "raffles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','eligibility_locked','drawn','published','cancelled')",
            name="ck_raffle_status",
        ),
        CheckConstraint("winner_count BETWEEN 1 AND 100", name="ck_raffle_winner_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    eligibility_rule: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    winner_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    eligibility: Mapped[list["RaffleEligibility"]] = relationship(
        back_populates="raffle", cascade="all, delete-orphan", order_by="RaffleEligibility.ordinal"
    )
    winners: Mapped[list["RaffleWinner"]] = relationship(
        back_populates="raffle", cascade="all, delete-orphan", order_by="RaffleWinner.draw_number"
    )


class RaffleEligibility(Base):
    __tablename__ = "raffle_eligibility"
    __table_args__ = (
        UniqueConstraint("raffle_id", "user_id", name="uq_raffle_eligibility_user"),
        UniqueConstraint("raffle_id", "ordinal", name="uq_raffle_eligibility_ordinal"),
        CheckConstraint("ordinal >= 1", name="ck_raffle_eligibility_ordinal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raffle_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raffles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attendance_evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

    raffle: Mapped[Raffle] = relationship(back_populates="eligibility")


class RaffleWinner(Base):
    __tablename__ = "raffle_winners"
    __table_args__ = (
        UniqueConstraint("raffle_id", "user_id", name="uq_raffle_winner_user"),
        UniqueConstraint("raffle_id", "draw_number", name="uq_raffle_winner_number"),
        UniqueConstraint("idempotency_key", name="uq_raffle_winner_idempotency"),
        CheckConstraint("draw_number >= 1", name="ck_raffle_winner_draw_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raffle_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raffles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    drawn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    drawn_by: Mapped[str] = mapped_column(String(36), nullable=False)
    draw_number: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    random_evidence: Mapped[str] = mapped_column(String(128), nullable=False)
    audit_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    raffle: Mapped[Raffle] = relationship(back_populates="winners")


class OutboxEvent(Base):
    __tablename__ = "raffle_outbox_events"
    __table_args__ = (CheckConstraint("attempts >= 0", name="ck_raffle_outbox_attempts"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    routing_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
