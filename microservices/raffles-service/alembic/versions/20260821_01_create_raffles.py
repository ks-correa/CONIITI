"""Create raffle, eligibility, winner and outbox tables.

Revision ID: 20260821_01
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "20260821_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raffles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("eligibility_rule", sa.JSON(), nullable=False),
        sa.Column("winner_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.CheckConstraint("status IN ('draft','eligibility_locked','drawn','published','cancelled')", name="ck_raffle_status"),
        sa.CheckConstraint("winner_count BETWEEN 1 AND 100", name="ck_raffle_winner_count"),
    )
    op.create_index("ix_raffles_status", "raffles", ["status"])
    op.create_table(
        "raffle_eligibility",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("raffle_id", sa.String(36), sa.ForeignKey("raffles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("attendance_evidence", sa.JSON(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("raffle_id", "user_id", name="uq_raffle_eligibility_user"),
        sa.UniqueConstraint("raffle_id", "ordinal", name="uq_raffle_eligibility_ordinal"),
        sa.CheckConstraint("ordinal >= 1", name="ck_raffle_eligibility_ordinal"),
    )
    op.create_index("ix_raffle_eligibility_raffle_id", "raffle_eligibility", ["raffle_id"])
    op.create_index("ix_raffle_eligibility_user_id", "raffle_eligibility", ["user_id"])
    op.create_table(
        "raffle_winners",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("raffle_id", sa.String(36), sa.ForeignKey("raffles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("drawn_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("drawn_by", sa.String(36), nullable=False),
        sa.Column("draw_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("random_evidence", sa.String(128), nullable=False),
        sa.Column("audit_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("raffle_id", "user_id", name="uq_raffle_winner_user"),
        sa.UniqueConstraint("raffle_id", "draw_number", name="uq_raffle_winner_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_raffle_winner_idempotency"),
        sa.UniqueConstraint("audit_hash", name="uq_raffle_winner_audit_hash"),
        sa.CheckConstraint("draw_number >= 1", name="ck_raffle_winner_draw_number"),
    )
    op.create_index("ix_raffle_winners_raffle_id", "raffle_winners", ["raffle_id"])
    op.create_index("ix_raffle_winners_user_id", "raffle_winners", ["user_id"])
    op.create_table(
        "raffle_outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("routing_key", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_raffle_outbox_attempts"),
    )
    op.create_index("ix_raffle_outbox_events_published_at", "raffle_outbox_events", ["published_at"])


def downgrade() -> None:
    op.drop_table("raffle_outbox_events")
    op.drop_table("raffle_winners")
    op.drop_table("raffle_eligibility")
    op.drop_table("raffles")
