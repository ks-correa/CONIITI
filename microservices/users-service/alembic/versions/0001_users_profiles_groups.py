"""Users baseline, extended profiles, groups and audit.

Revision ID: 0001_users
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_users"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("first_name", sa.String(120), nullable=True),
            sa.Column("last_name", sa.String(120), nullable=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column(
                "role",
                sa.Enum(
                    "external",
                    "university_community",
                    "staff",
                    "superuser",
                    name="userrole",
                    native_enum=False,
                ),
                nullable=False,
                server_default="external",
            ),
            sa.Column("institution", sa.String(255), nullable=True),
            sa.Column("career", sa.String(255), nullable=True),
            sa.Column("gender", sa.String(80), nullable=True),
            sa.Column("document", sa.String(100), nullable=True),
            sa.Column("institutional_code", sa.String(100), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_document", "users", ["document"], unique=True)
        op.create_index(
            "ix_users_institutional_code",
            "users",
            ["institutional_code"],
            unique=True,
        )
    else:
        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
        additions = (
            ("first_name", sa.String(120)),
            ("last_name", sa.String(120)),
            ("career", sa.String(255)),
            ("gender", sa.String(80)),
            ("document", sa.String(100)),
            ("institutional_code", sa.String(100)),
            ("updated_at", sa.DateTime(timezone=True)),
            ("profile_completed_at", sa.DateTime(timezone=True)),
        )
        for name, column_type in additions:
            if name not in columns:
                if name == "updated_at":
                    op.add_column(
                        "users",
                        sa.Column(name, column_type, nullable=False, server_default=sa.func.now()),
                    )
                else:
                    op.add_column("users", sa.Column(name, column_type, nullable=True))
        existing_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("users")}
        if "ix_users_document" not in existing_indexes:
            op.create_index("ix_users_document", "users", ["document"], unique=True)
        if "ix_users_institutional_code" not in existing_indexes:
            op.create_index("ix_users_institutional_code", "users", ["institutional_code"], unique=True)

    if "committee_members" not in _tables():
        op.create_table(
            "committee_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("nombre", sa.String(255), nullable=False),
            sa.Column("cargo", sa.String(255), nullable=False),
            sa.Column("institucion", sa.String(255), nullable=True),
            sa.Column("foto_url", sa.String(1000), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "groups" not in _tables():
        op.create_table(
            "groups",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_groups_name", "groups", ["name"], unique=True)

    if "group_memberships" not in _tables():
        op.create_table(
            "group_memberships",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "membership_role",
                sa.Enum(
                    "member",
                    "group_admin",
                    name="groupmembershiprole",
                    native_enum=False,
                ),
                nullable=False,
                server_default="member",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("added_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("group_id", "user_id", name="uq_group_membership"),
        )
        op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"])
        op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])

    if "group_audit_logs" not in _tables():
        op.create_table(
            "group_audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.String(36), nullable=False),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("subject_user_id", sa.String(36), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_group_audit_logs_group_id", "group_audit_logs", ["group_id"])
        op.create_index("ix_group_audit_logs_actor_id", "group_audit_logs", ["actor_id"])
        op.create_index("ix_group_audit_logs_occurred_at", "group_audit_logs", ["occurred_at"])


def downgrade() -> None:
    # Preserve profiles and audit history. Destructive rollbacks require an
    # explicit, reviewed data-retention migration.
    pass
