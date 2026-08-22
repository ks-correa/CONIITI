"""Schema histórico de Agenda previo a la integración.

La revisión es deliberadamente condicional: una base legacy creada con
``Base.metadata.create_all`` no tiene ``alembic_version`` y debe poder ejecutar
``alembic upgrade head`` sin recrear sus tablas. En una base vacía sí crea el
schema histórico. El downgrade del baseline es no-op para no destruir tablas
que Alembic no puede distinguir de las heredadas.
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_existing"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "speakers" not in existing_tables:
        op.create_table(
            "speakers",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("nombre", sa.String(255), nullable=False),
            sa.Column("afiliacion", sa.String(255), nullable=False, server_default=""),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("foto_url", sa.String(1000), nullable=True),
            sa.Column("es_principal", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("nombre", "afiliacion", name="uix_speaker_nombre_afiliacion"),
        )
        op.create_index("ix_speakers_id", "speakers", ["id"])
        op.create_index("ix_speakers_nombre", "speakers", ["nombre"])

    track = sa.Enum(
        "IA", "CIBERSEGURIDAD", "IOT", "DESARROLLO", "DATOS", "INNOVACION",
        name="sessiontrack",
    )
    event_type = sa.Enum("CONFERENCE", "WORKSHOP", "SYMPOSIUM", "PANEL", name="sessioneventtype")
    modality = sa.Enum("PRESENCIAL", "VIRTUAL", "HIBRIDO", name="sessionmodality")
    status = sa.Enum("NORMAL", "CAMBIO_SALON", "RETRASADO", name="sessionstatus")
    if "agenda_sessions" not in existing_tables:
        op.create_table(
            "agenda_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("titulo", sa.String(500), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("speaker_id", sa.Uuid(), nullable=False),
            sa.Column("track", track, nullable=False),
            sa.Column("event_type", event_type, nullable=False),
            sa.Column("dia", sa.String(10), nullable=False),
            sa.Column("hora_inicio", sa.String(5), nullable=False),
            sa.Column("hora_fin", sa.String(5), nullable=False),
            sa.Column("salon", sa.String(255), nullable=False),
            sa.Column("salon_anterior", sa.String(255), nullable=True),
            sa.Column("modalidad", modality, nullable=False),
            sa.Column("status_logistico", status, nullable=False, server_default="NORMAL"),
            sa.Column("link_virtual", sa.String(1000), nullable=True),
            sa.Column("link_verificado", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("cupos_totales", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inscritos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agenda_sessions_id", "agenda_sessions", ["id"])
        op.create_index("ix_agenda_sessions_titulo", "agenda_sessions", ["titulo"])
        op.create_index("ix_agenda_sessions_dia", "agenda_sessions", ["dia"])

    if "session_registrations" not in existing_tables:
        op.create_table(
            "session_registrations",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("session_id", sa.Uuid(), nullable=False),
            sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("user_id", "session_id"),
        )


def downgrade() -> None:
    # Baseline no destructivo: estas tablas pueden haber precedido a Alembic.
    pass
