"""Move Files metadata to relational storage and add site configuration."""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260821_0001"
down_revision = None
branch_labels = None
depends_on = None


DEFAULT_CONFIGURATION = {
    "event": {
        "title": "XI CONIITI 2026",
        "subtitle": "Congreso Internacional de Innovacion y Tendencias en Ingenieria",
        "description": "",
        "location_label": "Bogota, Colombia",
    },
    "guest_country": {
        "id": "italia",
        "country": "Italia",
        "colors": ["#009246", "#ffffff", "#ce2b37"],
        "site_accents_enabled": True,
        "agenda_particles_enabled": True,
    },
    "branding": {
        "logo_asset_id": None,
        "logo_url": None,
        "hero_asset_id": None,
        "hero_url": None,
    },
    "pages": {
        "home": {
            "title": "XI CONIITI 2026",
            "subtitle": "Congreso Internacional de Innovacion y Tendencias en Ingenieria.",
            "cta_label": "Ver agenda",
        },
        "about": {
            "title": "Acerca de CONIITI",
            "description": "Un punto de encuentro academico para explorar innovacion, tendencias y nuevas aproximaciones en ingenieria con vision internacional.",
        },
        "contact": {
            "title": "Contacto",
            "email": "coniiti@ucatolica.edu.co",
            "phone": "PBX: (601) 4433700",
            "address": "Bogota, carrera 13 # 47 - 30",
            "message": "Estamos disponibles para orientar tus consultas sobre el congreso.",
        },
        "speakers": {
            "title": "Conferencistas principales",
            "subtitle": "Conoce a los conferencistas invitados del Congreso CONIITI.",
            "show_organization": True,
        },
        "agenda": {
            "title": "Agenda",
            "subtitle": "Conferencias y talleres del Congreso CONIITI.",
            "show_filters": True,
            "columns": 3,
        },
    },
    "modules": {
        "agenda_visible": True,
        "gallery_visible": True,
        "speakers_visible": True,
        "memories_visible": True,
        "authors_visible": True,
        "committee_visible": True,
        "about_visible": True,
        "contact_visible": True,
        "payments_visible": True,
    },
}


def upgrade() -> None:
    op.create_table(
        "file_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False, unique=True),
        sa.Column("original_name", sa.String(512), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_file_assets_status", "file_assets", ["status"])
    op.create_index("ix_file_assets_created_at", "file_assets", ["created_at"])

    op.create_table(
        "file_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("ponente_nombre", sa.String(300), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("file_url", sa.String(1024), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("file_assets.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("original_name", sa.String(512), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_file_documents_category", "file_documents", ["category"])
    op.create_index("ix_file_documents_ponente_nombre", "file_documents", ["ponente_nombre"])
    op.create_index("ix_file_documents_session_id", "file_documents", ["session_id"])
    op.create_index("ix_file_documents_asset_id", "file_documents", ["asset_id"])

    op.create_table(
        "file_content_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("section", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("subtitle", sa.String(300), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(1024), nullable=True),
        sa.Column("link_url", sa.String(1024), nullable=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("file_assets.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("media_type", sa.String(32), nullable=False, server_default="image"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_file_content_cards_section", "file_content_cards", ["section"])
    op.create_index("ix_file_content_cards_asset_id", "file_content_cards", ["asset_id"])
    op.create_index("ix_file_content_cards_is_active", "file_content_cards", ["is_active"])

    op.create_table(
        "file_asset_references",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("file_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_service", sa.String(100), nullable=False),
        sa.Column("owner_type", sa.String(100), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "asset_id", "owner_service", "owner_type", "owner_id",
            name="uq_file_asset_reference_owner",
        ),
    )
    op.create_index("ix_file_asset_references_asset_id", "file_asset_references", ["asset_id"])

    revisions = op.create_table(
        "file_site_config_revisions",
        sa.Column("revision", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("change_summary", sa.String(500), nullable=False),
    )
    op.create_index("ix_file_site_config_revisions_created_at", "file_site_config_revisions", ["created_at"])
    current = op.create_table(
        "file_site_config_current",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "current_revision",
            sa.Integer(),
            sa.ForeignKey("file_site_config_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.bulk_insert(revisions, [{
        "schema_version": 1,
        "payload": DEFAULT_CONFIGURATION,
        "created_at": datetime.now(timezone.utc),
        "created_by": "00000000-0000-0000-0000-000000000000",
        "change_summary": "Configuracion inicial",
    }])
    op.bulk_insert(current, [{"id": 1, "current_revision": 1}])


def downgrade() -> None:
    op.drop_table("file_site_config_current")
    op.drop_index("ix_file_site_config_revisions_created_at", table_name="file_site_config_revisions")
    op.drop_table("file_site_config_revisions")
    op.drop_index("ix_file_asset_references_asset_id", table_name="file_asset_references")
    op.drop_table("file_asset_references")
    op.drop_index("ix_file_content_cards_is_active", table_name="file_content_cards")
    op.drop_index("ix_file_content_cards_asset_id", table_name="file_content_cards")
    op.drop_index("ix_file_content_cards_section", table_name="file_content_cards")
    op.drop_table("file_content_cards")
    op.drop_index("ix_file_documents_asset_id", table_name="file_documents")
    op.drop_index("ix_file_documents_session_id", table_name="file_documents")
    op.drop_index("ix_file_documents_ponente_nombre", table_name="file_documents")
    op.drop_index("ix_file_documents_category", table_name="file_documents")
    op.drop_table("file_documents")
    op.drop_index("ix_file_assets_created_at", table_name="file_assets")
    op.drop_index("ix_file_assets_status", table_name="file_assets")
    op.drop_table("file_assets")
