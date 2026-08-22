"""Calendario, sedes, multimedia, integridad y asistencia."""
import uuid

from alembic import op
import sqlalchemy as sa


revision = "0002_integration"
down_revision = "0001_existing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("capacity > 0", name="ck_venues_capacity_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_venues_id", "venues", ["id"])
    op.create_index("ix_venues_name", "venues", ["name"])
    op.create_index("ix_venues_is_active", "venues", ["is_active"])

    op.add_column("agenda_sessions", sa.Column("venue_id", sa.Uuid(), nullable=True))
    op.add_column(
        "agenda_sessions",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agenda_sessions_venue_id", "agenda_sessions", ["venue_id"])
    op.create_foreign_key(
        "fk_agenda_sessions_venue_id", "agenda_sessions", "venues",
        ["venue_id"], ["id"], ondelete="RESTRICT",
    )

    connection = op.get_bind()
    # El contador legacy podía divergir; la tabla de asociación es la fuente real.
    connection.execute(sa.text(
        "UPDATE agenda_sessions AS s SET inscritos = "
        "(SELECT COUNT(*) FROM session_registrations sr WHERE sr.session_id = s.id)"
    ))
    connection.execute(sa.text(
        "UPDATE agenda_sessions SET cupos_totales = 0 WHERE cupos_totales < 0"
    ))
    connection.execute(sa.text(
        "UPDATE agenda_sessions SET cupos_totales = inscritos "
        "WHERE cupos_totales > 0 AND inscritos > cupos_totales"
    ))
    op.create_check_constraint(
        "ck_agenda_sessions_capacity_nonnegative",
        "agenda_sessions", "cupos_totales >= 0",
    )
    op.create_check_constraint(
        "ck_agenda_sessions_registered_nonnegative",
        "agenda_sessions", "inscritos >= 0",
    )
    op.create_check_constraint(
        "ck_agenda_sessions_registered_within_capacity",
        "agenda_sessions", "cupos_totales = 0 OR inscritos <= cupos_totales",
    )
    rooms = connection.execute(sa.text(
        "SELECT salon, GREATEST(COALESCE(MAX(cupos_totales), 0), 1) AS capacity "
        "FROM agenda_sessions GROUP BY salon"
    )).mappings().all()
    for room in rooms:
        venue_id = uuid.uuid4()
        connection.execute(sa.text(
            "INSERT INTO venues (id, name, capacity, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :capacity, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"id": venue_id, "name": room["salon"], "capacity": room["capacity"]})
        connection.execute(sa.text(
            "UPDATE agenda_sessions SET venue_id = :venue_id WHERE salon = :name"
        ), {"venue_id": venue_id, "name": room["salon"]})

    connection.execute(sa.text(
        "DELETE FROM session_registrations sr WHERE NOT EXISTS "
        "(SELECT 1 FROM agenda_sessions s WHERE s.id = sr.session_id)"
    ))
    op.create_foreign_key(
        "fk_session_registrations_session_id", "session_registrations", "agenda_sessions",
        ["session_id"], ["id"], ondelete="CASCADE",
    )

    op.create_table(
        "agenda_configuration",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("edition_label", sa.String(255), nullable=False),
        sa.Column("conference_days", sa.JSON(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_agenda_configuration_version_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    config_table = sa.table(
        "agenda_configuration",
        sa.column("id", sa.String), sa.column("edition_label", sa.String),
        sa.column("conference_days", sa.JSON), sa.column("timezone", sa.String),
        sa.column("version", sa.Integer),
    )
    op.bulk_insert(config_table, [{
        "id": "default", "edition_label": "CONIITI 2026",
        "conference_days": ["2026-10-01", "2026-10-02", "2026-10-03"],
        "timezone": "America/Bogota", "version": 1,
    }])

    op.create_table(
        "venue_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("alt_text", sa.String(500), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("external_url", sa.String(2000), nullable=True),
        sa.Column("resolved_url", sa.String(2000), nullable=True),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("captions_asset_id", sa.Uuid(), nullable=True),
        sa.Column("captions_url", sa.String(2000), nullable=True),
        sa.Column("captions_resolved_url", sa.String(2000), nullable=True),
        sa.Column("transcript_asset_id", sa.Uuid(), nullable=True),
        sa.Column("transcript_url", sa.String(2000), nullable=True),
        sa.Column("transcript_resolved_url", sa.String(2000), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("state", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.CheckConstraint("display_order >= 0", name="ck_venue_resources_display_order_nonnegative"),
        sa.CheckConstraint(
            "(asset_id IS NOT NULL AND external_url IS NULL) OR "
            "(asset_id IS NULL AND external_url IS NOT NULL)",
            name="ck_venue_resources_exactly_one_source",
        ),
        sa.CheckConstraint(
            "captions_asset_id IS NULL OR captions_url IS NULL",
            name="ck_venue_resources_captions_one_source",
        ),
        sa.CheckConstraint(
            "transcript_asset_id IS NULL OR transcript_url IS NULL",
            name="ck_venue_resources_transcript_one_source",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_resources_id", "venue_resources", ["id"])
    op.create_index("ix_venue_resources_asset_id", "venue_resources", ["asset_id"])
    op.create_index(
        "ix_venue_resources_captions_asset_id", "venue_resources", ["captions_asset_id"],
    )
    op.create_index(
        "ix_venue_resources_transcript_asset_id", "venue_resources", ["transcript_asset_id"],
    )
    op.create_index("ix_venue_resources_venue_id", "venue_resources", ["venue_id"])
    op.create_index("ix_venue_resources_state", "venue_resources", ["state"])
    op.create_index("ix_venue_resources_venue_order", "venue_resources", ["venue_id", "display_order"])

    op.create_table(
        "asset_reference_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("slot", sa.String(16), nullable=False, server_default="primary"),
        sa.Column("finalize_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["resource_id"], ["venue_resources.id"], ondelete="CASCADE"),
        sa.CheckConstraint("attempts >= 0", name="ck_asset_reference_outbox_attempts_nonnegative"),
        sa.CheckConstraint(
            "slot IN ('primary', 'captions', 'transcript')",
            name="ck_asset_reference_outbox_slot",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_reference_outbox_asset_id", "asset_reference_outbox", ["asset_id"])
    op.create_index("ix_asset_reference_outbox_resource_id", "asset_reference_outbox", ["resource_id"])
    op.create_index("ix_asset_reference_outbox_status", "asset_reference_outbox", ["status"])
    op.create_index("ix_asset_reference_outbox_ready", "asset_reference_outbox", ["status", "next_attempt_at"])

    op.create_table(
        "attendance_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("jti_hash", sa.String(64), nullable=False),
        sa.Column("issued_by", sa.Uuid(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["session_id"], ["agenda_sessions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("max_uses > 0", name="ck_attendance_tokens_max_uses_positive"),
        sa.CheckConstraint("used_count >= 0", name="ck_attendance_tokens_used_count_nonnegative"),
        sa.CheckConstraint("used_count <= max_uses", name="ck_attendance_tokens_used_within_limit"),
        sa.CheckConstraint("key_version > 0", name="ck_attendance_tokens_key_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti_hash", name="uq_attendance_token_jti_hash"),
    )
    op.create_index("ix_attendance_token_session_expiry", "attendance_verification_tokens", ["session_id", "expires_at"])

    op.create_table(
        "session_attendance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_by", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("confirmation_note", sa.String(500), nullable=True),
        sa.Column("verification_token_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["agenda_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verification_token_id"], ["attendance_verification_tokens.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("method IN ('qr', 'manual')", name="ck_session_attendance_method"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_attendance_session_user"),
    )
    op.create_index("ix_session_attendance_session_id", "session_attendance", ["session_id"])
    op.create_index("ix_session_attendance_user_id", "session_attendance", ["user_id"])
    op.create_index("ix_attendance_confirmed_at", "session_attendance", ["confirmed_at"])

    op.create_table(
        "agenda_event_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("routing_key", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_agenda_event_outbox_attempts_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_agenda_event_outbox_event_id"),
    )
    op.create_index("ix_agenda_event_outbox_ready", "agenda_event_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_agenda_event_outbox_ready", table_name="agenda_event_outbox")
    op.drop_table("agenda_event_outbox")
    op.drop_index("ix_attendance_confirmed_at", table_name="session_attendance")
    op.drop_index("ix_session_attendance_user_id", table_name="session_attendance")
    op.drop_index("ix_session_attendance_session_id", table_name="session_attendance")
    op.drop_table("session_attendance")
    op.drop_index("ix_attendance_token_session_expiry", table_name="attendance_verification_tokens")
    op.drop_table("attendance_verification_tokens")
    op.drop_index("ix_asset_reference_outbox_ready", table_name="asset_reference_outbox")
    op.drop_index("ix_asset_reference_outbox_status", table_name="asset_reference_outbox")
    op.drop_index("ix_asset_reference_outbox_resource_id", table_name="asset_reference_outbox")
    op.drop_index("ix_asset_reference_outbox_asset_id", table_name="asset_reference_outbox")
    op.drop_table("asset_reference_outbox")
    op.drop_index("ix_venue_resources_venue_order", table_name="venue_resources")
    op.drop_index("ix_venue_resources_state", table_name="venue_resources")
    op.drop_index("ix_venue_resources_venue_id", table_name="venue_resources")
    op.drop_index("ix_venue_resources_transcript_asset_id", table_name="venue_resources")
    op.drop_index("ix_venue_resources_captions_asset_id", table_name="venue_resources")
    op.drop_index("ix_venue_resources_asset_id", table_name="venue_resources")
    op.drop_index("ix_venue_resources_id", table_name="venue_resources")
    op.drop_table("venue_resources")
    op.drop_table("agenda_configuration")
    op.drop_constraint("fk_session_registrations_session_id", "session_registrations", type_="foreignkey")
    op.drop_constraint("ck_agenda_sessions_registered_within_capacity", "agenda_sessions", type_="check")
    op.drop_constraint("ck_agenda_sessions_registered_nonnegative", "agenda_sessions", type_="check")
    op.drop_constraint("ck_agenda_sessions_capacity_nonnegative", "agenda_sessions", type_="check")
    op.drop_constraint("fk_agenda_sessions_venue_id", "agenda_sessions", type_="foreignkey")
    op.drop_index("ix_agenda_sessions_venue_id", table_name="agenda_sessions")
    op.drop_column("agenda_sessions", "updated_at")
    op.drop_column("agenda_sessions", "venue_id")
    op.drop_index("ix_venues_is_active", table_name="venues")
    op.drop_index("ix_venues_name", table_name="venues")
    op.drop_index("ix_venues_id", table_name="venues")
    op.drop_table("venues")
