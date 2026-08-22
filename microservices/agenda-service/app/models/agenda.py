import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, Index, Integer,
    String, Table, Text, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus(str, enum.Enum):
    NORMAL = "Normal"
    CAMBIO_SALON = "Cambio de Salón"
    RETRASADO = "Retrasado"


class SessionModality(str, enum.Enum):
    PRESENCIAL = "Presencial"
    VIRTUAL = "Virtual"
    HIBRIDO = "Híbrido"


class SessionTrack(str, enum.Enum):
    IA = "Inteligencia Artificial"
    CIBERSEGURIDAD = "Ciberseguridad"
    IOT = "Internet de las Cosas"
    DESARROLLO = "Desarrollo de Software"
    DATOS = "Ciencia de Datos"
    INNOVACION = "Innovación y Tendencias"


class SessionEventType(str, enum.Enum):
    CONFERENCE = "Conferencia"
    WORKSHOP = "Taller"
    SYMPOSIUM = "Simposio"
    PANEL = "Panel"


class ResourceType(str, enum.Enum):
    VIDEO = "video"
    IMAGE = "image"
    DOCUMENT = "document"
    LINK = "link"
    POSTER = "poster"


class ResourceState(str, enum.Enum):
    PENDING_ASSET = "pending_asset"
    ACTIVE = "active"
    PENDING_DELETE = "pending_delete"
    TOMBSTONED = "tombstoned"
    ERROR = "error"


class AttendanceMethod(str, enum.Enum):
    QR = "qr"
    MANUAL = "manual"


session_registrations = Table(
    "session_registrations",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "session_id", Uuid(as_uuid=True),
        ForeignKey("agenda_sessions.id", ondelete="CASCADE"), primary_key=True,
    ),
    Column("registered_at", DateTime(timezone=True), nullable=False, default=utcnow),
)


class Speaker(Base):
    __tablename__ = "speakers"
    __table_args__ = (
        UniqueConstraint("nombre", "afiliacion", name="uix_speaker_nombre_afiliacion"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    nombre = Column(String(255), nullable=False, index=True)
    afiliacion = Column(String(255), nullable=False, default="")
    descripcion = Column(Text, nullable=True)
    foto_url = Column(String(1000), nullable=True)
    es_principal = Column(Boolean, nullable=False, default=False)
    sesiones = relationship("AgendaSession", back_populates="speaker")

    def __repr__(self) -> str:
        return f"<Speaker id={self.id} nombre={self.nombre}>"


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_venues_capacity_positive"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    capacity = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by = Column(Uuid(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("AgendaSession", back_populates="venue")
    resources = relationship(
        "VenueResource", back_populates="venue", cascade="all, delete-orphan",
        order_by="VenueResource.display_order, VenueResource.created_at",
    )

    @property
    def active_resources(self):
        return [
            resource for resource in self.resources
            if resource.is_active and resource.deleted_at is None
            and resource.state == ResourceState.ACTIVE.value
        ]


class VenueResource(Base):
    __tablename__ = "venue_resources"
    __table_args__ = (
        Index("ix_venue_resources_venue_order", "venue_id", "display_order"),
        CheckConstraint("display_order >= 0", name="ck_venue_resources_display_order_nonnegative"),
        CheckConstraint(
            "(asset_id IS NOT NULL AND external_url IS NULL) OR "
            "(asset_id IS NULL AND external_url IS NOT NULL)",
            name="ck_venue_resources_exactly_one_source",
        ),
        CheckConstraint(
            "captions_asset_id IS NULL OR captions_url IS NULL",
            name="ck_venue_resources_captions_one_source",
        ),
        CheckConstraint(
            "transcript_asset_id IS NULL OR transcript_url IS NULL",
            name="ck_venue_resources_transcript_one_source",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    venue_id = Column(
        Uuid(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    resource_type = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    alt_text = Column(String(500), nullable=True)
    asset_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    external_url = Column(String(2000), nullable=True)
    resolved_url = Column(String(2000), nullable=True)
    mime_type = Column(String(255), nullable=True)
    captions_asset_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    captions_url = Column(String(2000), nullable=True)
    captions_resolved_url = Column(String(2000), nullable=True)
    transcript_asset_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    transcript_url = Column(String(2000), nullable=True)
    transcript_resolved_url = Column(String(2000), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    state = Column(String(32), nullable=False, default=ResourceState.ACTIVE.value, index=True)
    created_by = Column(Uuid(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    venue = relationship("Venue", back_populates="resources")

    @property
    def url(self) -> str | None:
        return self.resolved_url or self.external_url

    @property
    def effective_captions_url(self) -> str | None:
        return self.captions_resolved_url or self.captions_url

    @property
    def effective_transcript_url(self) -> str | None:
        return self.transcript_resolved_url or self.transcript_url


class AgendaConfiguration(Base):
    __tablename__ = "agenda_configuration"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_agenda_configuration_version_positive"),
    )

    id = Column(String(32), primary_key=True, default="default")
    edition_label = Column(String(255), nullable=False, default="CONIITI 2026")
    conference_days = Column(
        JSON, nullable=False,
        default=lambda: ["2026-10-01", "2026-10-02", "2026-10-03"],
    )
    timezone = Column(String(64), nullable=False, default="America/Bogota")
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    updated_by = Column(Uuid(as_uuid=True), nullable=True)


class AgendaSession(Base):
    __tablename__ = "agenda_sessions"
    __table_args__ = (
        CheckConstraint("cupos_totales >= 0", name="ck_agenda_sessions_capacity_nonnegative"),
        CheckConstraint("inscritos >= 0", name="ck_agenda_sessions_registered_nonnegative"),
        CheckConstraint(
            "cupos_totales = 0 OR inscritos <= cupos_totales",
            name="ck_agenda_sessions_registered_within_capacity",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    titulo = Column(String(500), nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    speaker_id = Column(Uuid(as_uuid=True), ForeignKey("speakers.id"), nullable=False)
    speaker = relationship("Speaker", back_populates="sesiones")

    @property
    def ponente(self) -> str:
        return self.speaker.nombre if self.speaker else ""

    @property
    def afiliacion(self):
        if not self.speaker:
            return None
        return self.speaker.afiliacion if self.speaker.afiliacion.strip() else None

    @property
    def descripcion_ponente(self) -> str | None:
        return self.speaker.descripcion if self.speaker else None

    @property
    def foto_ponente_url(self) -> str | None:
        return self.speaker.foto_url if self.speaker else None

    @property
    def es_conferencista_principal(self) -> bool:
        return self.speaker.es_principal if self.speaker else False

    @property
    def timestamp_actualizacion(self) -> datetime:
        return self.updated_at

    track = Column(Enum(SessionTrack), nullable=False)
    event_type = Column(Enum(SessionEventType), nullable=False)
    dia = Column(String(10), nullable=False, index=True)
    hora_inicio = Column(String(5), nullable=False)
    hora_fin = Column(String(5), nullable=False)
    salon = Column(String(255), nullable=False)
    salon_anterior = Column(String(255), nullable=True)
    venue_id = Column(
        Uuid(as_uuid=True), ForeignKey("venues.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    venue = relationship("Venue", back_populates="sessions")
    modalidad = Column(Enum(SessionModality), nullable=False)
    status_logistico = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.NORMAL)
    link_virtual = Column(String(1000), nullable=True)
    link_verificado = Column(Boolean, nullable=False, default=False)
    cupos_totales = Column(Integer, nullable=False, default=0)
    inscritos = Column(Integer, nullable=False, default=0)
    created_by = Column(Uuid(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<AgendaSession id={self.id} titulo={self.titulo[:40]}>"


class AssetReferenceOutbox(Base):
    __tablename__ = "asset_reference_outbox"
    __table_args__ = (
        Index("ix_asset_reference_outbox_ready", "status", "next_attempt_at"),
        CheckConstraint("attempts >= 0", name="ck_asset_reference_outbox_attempts_nonnegative"),
        CheckConstraint(
            "slot IN ('primary', 'captions', 'transcript')",
            name="ck_asset_reference_outbox_slot",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(
        Uuid(as_uuid=True), ForeignKey("venue_resources.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    asset_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    operation = Column(String(16), nullable=False)
    slot = Column(String(16), nullable=False, default="primary")
    finalize_delete = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    resource = relationship("VenueResource")


class AttendanceVerificationToken(Base):
    __tablename__ = "attendance_verification_tokens"
    __table_args__ = (
        UniqueConstraint("jti_hash", name="uq_attendance_token_jti_hash"),
        Index("ix_attendance_token_session_expiry", "session_id", "expires_at"),
        CheckConstraint("max_uses > 0", name="ck_attendance_tokens_max_uses_positive"),
        CheckConstraint("used_count >= 0", name="ck_attendance_tokens_used_count_nonnegative"),
        CheckConstraint("used_count <= max_uses", name="ck_attendance_tokens_used_within_limit"),
        CheckConstraint("key_version > 0", name="ck_attendance_tokens_key_version_positive"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        Uuid(as_uuid=True), ForeignKey("agenda_sessions.id", ondelete="RESTRICT"), nullable=False,
    )
    jti_hash = Column(String(64), nullable=False)
    issued_by = Column(Uuid(as_uuid=True), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    max_uses = Column(Integer, nullable=False, default=1)
    used_count = Column(Integer, nullable=False, default=0)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    key_version = Column(Integer, nullable=False, default=1)


class SessionAttendance(Base):
    __tablename__ = "session_attendance"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_attendance_session_user"),
        Index("ix_attendance_confirmed_at", "confirmed_at"),
        CheckConstraint("method IN ('qr', 'manual')", name="ck_session_attendance_method"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        Uuid(as_uuid=True), ForeignKey("agenda_sessions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    user_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    confirmed_by = Column(Uuid(as_uuid=True), nullable=False)
    method = Column(String(20), nullable=False)
    confirmation_note = Column(String(500), nullable=True)
    verification_token_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_verification_tokens.id", ondelete="RESTRICT"), nullable=True,
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(500), nullable=True)
    session = relationship("AgendaSession")
    verification_token = relationship("AttendanceVerificationToken")


class DomainEventOutbox(Base):
    __tablename__ = "agenda_event_outbox"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_agenda_event_outbox_event_id"),
        Index("ix_agenda_event_outbox_ready", "status", "next_attempt_at"),
        CheckConstraint("attempts >= 0", name="ck_agenda_event_outbox_attempts_nonnegative"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(Uuid(as_uuid=True), nullable=False)
    routing_key = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)
