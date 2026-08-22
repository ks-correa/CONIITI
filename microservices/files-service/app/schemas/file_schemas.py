from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _safe_optional_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith("/") and not normalized.startswith("//"):
        return normalized
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL debe usar http(s) o ser una ruta interna absoluta.")
    return normalized


def _relative_luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    adjusted = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * adjusted[0] + 0.7152 * adjusted[1] + 0.0722 * adjusted[2]


def _contrast(left: str, right: str) -> float:
    high, low = sorted((_relative_luminance(left), _relative_luminance(right)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AssetRead(StrictModel):
    id: str
    filename: str
    original_name: str
    url: str
    content_type: str
    download_url: str
    mime_type: str
    size_bytes: int = 0
    checksum_sha256: str
    status: Literal["ready", "quarantined", "deleted"] = "ready"
    is_public: bool = True
    created_at: datetime


class AssetReferenceRead(StrictModel):
    asset_id: str
    owner_service: str
    owner_type: str
    owner_id: str
    created_at: datetime


class DocumentCreate(StrictModel):
    titulo: str = Field(min_length=1, max_length=300)
    descripcion: str | None = Field(default=None, max_length=5000)
    category: Literal["sistema", "ponente"]
    ponente_nombre: str | None = Field(default=None, max_length=300)
    session_id: str | None = Field(default=None, max_length=64)
    file_url: str = Field(min_length=1, max_length=1024)
    asset_id: str | None = None
    original_name: str | None = Field(default=None, max_length=512)
    sort_order: int = Field(default=0, ge=-10000, le=10000)

    _validate_file_url = field_validator("file_url", mode="before")(_safe_optional_url)


class DocumentRead(DocumentCreate):
    id: str
    created_at: datetime


class ContentCardCreate(StrictModel):
    section: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    subtitle: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1900, le=2200)
    description: str | None = Field(default=None, max_length=10000)
    image_url: str | None = Field(default=None, max_length=1024)
    link_url: str | None = Field(default=None, max_length=1024)
    asset_id: str | None = None
    media_type: Literal["image", "video", "document", "link"] = "image"
    is_active: bool = True
    sort_order: int = Field(default=0, ge=-10000, le=10000)

    _validate_image_url = field_validator("image_url", mode="before")(_safe_optional_url)
    _validate_link_url = field_validator("link_url", mode="before")(_safe_optional_url)


class ContentCardRead(ContentCardCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class EventConfiguration(StrictModel):
    title: str = Field(default="XI CONIITI 2026", min_length=1, max_length=160)
    subtitle: str = Field(
        default="Congreso Internacional de Innovacion y Tendencias en Ingenieria",
        max_length=300,
    )
    description: str = Field(default="", max_length=3000)
    location_label: str = Field(default="Bogota, Colombia", max_length=200)


class GuestCountryConfiguration(StrictModel):
    id: str = Field(default="italia", min_length=1, max_length=60)
    country: str = Field(default="Italia", min_length=1, max_length=100)
    colors: list[str] = Field(default_factory=lambda: ["#009246", "#ffffff", "#ce2b37"])
    site_accents_enabled: bool = True
    agenda_particles_enabled: bool = True

    @field_validator("colors")
    @classmethod
    def validate_colors(cls, value):
        if len(value) != 3:
            raise ValueError("Se requieren exactamente tres colores.")
        normalized = []
        for color in value:
            color = color.strip().lower()
            if len(color) != 7 or not color.startswith("#"):
                raise ValueError("Los colores deben tener formato hexadecimal #RRGGBB.")
            try:
                int(color[1:], 16)
            except ValueError as exc:
                raise ValueError("Los colores deben tener formato hexadecimal #RRGGBB.") from exc
            normalized.append(color)
        if max(_contrast(color, "#ffffff") for color in normalized) < 3:
            raise ValueError("La paleta necesita un color visible sobre fondo blanco.")
        if max(_contrast(color, "#0d2b4e") for color in normalized) < 3:
            raise ValueError("La paleta necesita un color visible sobre el azul institucional.")
        return normalized


class BrandingConfiguration(StrictModel):
    logo_asset_id: str | None = None
    logo_url: str | None = None
    hero_asset_id: str | None = None
    hero_url: str | None = None

    _validate_logo_url = field_validator("logo_url", mode="before")(_safe_optional_url)
    _validate_hero_url = field_validator("hero_url", mode="before")(_safe_optional_url)


class HomePageConfiguration(StrictModel):
    title: str = Field(default="XI CONIITI 2026", max_length=200)
    subtitle: str = Field(
        default="Congreso Internacional de Innovacion y Tendencias en Ingenieria.",
        max_length=500,
    )
    cta_label: str = Field(default="Ver agenda", max_length=80)


class AboutPageConfiguration(StrictModel):
    title: str = Field(default="Acerca de CONIITI", max_length=200)
    description: str = Field(
        default="Un punto de encuentro academico para explorar innovacion, tendencias y nuevas aproximaciones en ingenieria con vision internacional.",
        max_length=3000,
    )


class ContactPageConfiguration(StrictModel):
    title: str = Field(default="Contacto", max_length=200)
    email: str = Field(default="coniiti@ucatolica.edu.co", max_length=320)
    phone: str = Field(default="PBX: (601) 4433700", max_length=100)
    address: str = Field(default="Bogota, carrera 13 # 47 - 30", max_length=300)
    message: str = Field(
        default="Estamos disponibles para orientar tus consultas sobre el congreso.",
        max_length=1000,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or "." not in normalized.rsplit("@", 1)[1]:
            raise ValueError("Correo electronico invalido.")
        return normalized


class SpeakersPageConfiguration(StrictModel):
    title: str = Field(default="Conferencistas principales", max_length=200)
    subtitle: str = Field(
        default="Conoce a los conferencistas invitados del Congreso CONIITI.",
        max_length=500,
    )
    show_organization: bool = True


class AgendaPageConfiguration(StrictModel):
    title: str = Field(default="Agenda", max_length=200)
    subtitle: str = Field(default="Conferencias y talleres del Congreso CONIITI.", max_length=500)
    show_filters: bool = True
    columns: int = Field(default=3, ge=1, le=4)


class PageConfiguration(StrictModel):
    home: HomePageConfiguration = Field(default_factory=HomePageConfiguration)
    about: AboutPageConfiguration = Field(default_factory=AboutPageConfiguration)
    contact: ContactPageConfiguration = Field(default_factory=ContactPageConfiguration)
    speakers: SpeakersPageConfiguration = Field(default_factory=SpeakersPageConfiguration)
    agenda: AgendaPageConfiguration = Field(default_factory=AgendaPageConfiguration)


class ModuleVisibility(StrictModel):
    agenda_visible: bool = True
    gallery_visible: bool = True
    speakers_visible: bool = True
    memories_visible: bool = True
    authors_visible: bool = True
    committee_visible: bool = True
    about_visible: bool = True
    contact_visible: bool = True
    payments_visible: bool = True


class SiteConfigurationPayload(StrictModel):
    event: EventConfiguration = Field(default_factory=EventConfiguration)
    guest_country: GuestCountryConfiguration = Field(default_factory=GuestCountryConfiguration)
    branding: BrandingConfiguration = Field(default_factory=BrandingConfiguration)
    pages: PageConfiguration = Field(default_factory=PageConfiguration)
    modules: ModuleVisibility = Field(default_factory=ModuleVisibility)


class SiteConfigurationUpdate(StrictModel):
    configuration: SiteConfigurationPayload
    change_summary: str = Field(default="Actualizacion de configuracion", min_length=3, max_length=500)


class SiteConfigurationRollback(StrictModel):
    change_summary: str = Field(default="Rollback de configuracion", min_length=3, max_length=500)


class SiteConfigurationRead(SiteConfigurationPayload):
    revision: int
    schema_version: int
    created_at: datetime


class SiteConfigurationRevisionRead(SiteConfigurationRead):
    created_by: str
    change_summary: str
