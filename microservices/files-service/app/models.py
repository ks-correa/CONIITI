from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "file_assets"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False, unique=True)
    original_name = Column(String(512), nullable=False)
    url = Column(String(1024), nullable=False)
    content_type = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    checksum_sha256 = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="ready", index=True)
    is_public = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    @property
    def download_url(self):
        return self.url

    @property
    def mime_type(self):
        return self.content_type


class Document(Base):
    __tablename__ = "file_documents"

    id = Column(String(36), primary_key=True)
    titulo = Column(String(300), nullable=False)
    descripcion = Column(Text, nullable=True)
    category = Column(String(32), nullable=False, index=True)
    ponente_nombre = Column(String(300), nullable=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    file_url = Column(String(1024), nullable=False)
    asset_id = Column(
        String(36),
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    original_name = Column(String(512), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ContentCard(Base):
    __tablename__ = "file_content_cards"

    id = Column(String(36), primary_key=True)
    section = Column(String(64), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    subtitle = Column(String(300), nullable=True)
    year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)
    link_url = Column(String(1024), nullable=True)
    asset_id = Column(
        String(36),
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    media_type = Column(String(32), nullable=False, default="image")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AssetReference(Base):
    __tablename__ = "file_asset_references"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "owner_service",
            "owner_type",
            "owner_id",
            name="uq_file_asset_reference_owner",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(
        String(36),
        ForeignKey("file_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_service = Column(String(100), nullable=False)
    owner_type = Column(String(100), nullable=False)
    owner_id = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SiteConfigurationRevision(Base):
    __tablename__ = "file_site_config_revisions"

    revision = Column(Integer, primary_key=True, autoincrement=True)
    schema_version = Column(Integer, nullable=False, default=1)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    created_by = Column(String(36), nullable=False)
    change_summary = Column(String(500), nullable=False)


class SiteConfigurationCurrent(Base):
    __tablename__ = "file_site_config_current"

    id = Column(Integer, primary_key=True, default=1)
    current_revision = Column(
        Integer,
        ForeignKey("file_site_config_revisions.revision", ondelete="RESTRICT"),
        nullable=False,
    )
