"""Auth baseline and revocable session versions.

Revision ID: 0001_auth
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_auth"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "auth_users" not in tables:
        op.create_table(
            "auth_users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("email", name="uq_auth_users_email"),
        )
        op.create_index("ix_auth_users_email", "auth_users", ["email"], unique=True)
    else:
        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("auth_users")}
        if "session_version" not in columns:
            op.add_column(
                "auth_users",
                sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            )

    tables = _tables()
    if "otp_codes" not in tables:
        op.create_table(
            "otp_codes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(6), nullable=False),
            sa.Column(
                "purpose",
                sa.Enum("REGISTER", "LOGIN", name="otppurpose"),
                nullable=False,
            ),
            sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_otp_codes_user_id", "otp_codes", ["user_id"])

    if "password_reset_tokens" not in _tables():
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_hash"),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    # The baseline intentionally preserves account data. A destructive rollback
    # must be an explicit operational migration, never an automatic downgrade.
    pass
