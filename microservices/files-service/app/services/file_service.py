import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetReference,
    ContentCard,
    Document,
    SiteConfigurationCurrent,
    SiteConfigurationRevision,
)
from app.repositories.file_storage import (
    FilesStorageConfig,
    JsonRecordStore,
    LegacyJsonMetadataImporter,
    LocalBinaryStorage,
    build_storage_config,
)
from app.schemas.file_schemas import (
    ContentCardCreate,
    DocumentCreate,
    SiteConfigurationPayload,
)


EXTENSION_MIME_TYPES = {
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "mov": "video/quicktime",
    "mp4": "video/mp4",
    "pdf": "application/pdf",
    "png": "image/png",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "vtt": "text/vtt",
    "webm": "video/webm",
    "webp": "image/webp",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
SAFE_OWNER_PART = re.compile(r"^[a-zA-Z0-9_.:-]{1,100}$")
SYSTEM_ACTOR = "00000000-0000-0000-0000-000000000000"


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _default_config_payload() -> dict:
    return _model_dump(SiteConfigurationPayload())


def _detect_content_type(extension: str, header: bytes) -> str | None:
    if extension == "png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if extension in {"jpg", "jpeg"} and header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if extension == "gif" and header[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if extension == "webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if extension == "pdf" and header.startswith(b"%PDF-"):
        return "application/pdf"
    if extension == "webm" and header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if extension in {"mp4", "mov"} and len(header) >= 12 and header[4:8] == b"ftyp":
        brands = header[8:16]
        if extension == "mov" and (b"qt" in brands or b"qt" in header[:32]):
            return "video/quicktime"
        return "video/mp4" if extension == "mp4" else "video/quicktime"
    if extension in {"docx", "xlsx", "pptx"} and header.startswith(b"PK\x03\x04"):
        return EXTENSION_MIME_TYPES[extension]
    if extension in {"doc", "xls", "ppt"} and header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return EXTENSION_MIME_TYPES[extension]
    if extension in {"txt", "csv"} and b"\x00" not in header:
        return EXTENSION_MIME_TYPES[extension]
    if extension == "vtt" and (
        header.startswith(b"WEBVTT") or header.startswith(b"\xef\xbb\xbfWEBVTT")
    ):
        return "text/vtt"
    return None


class FilesApplicationService:
    def __init__(self, config: FilesStorageConfig, binary_storage: LocalBinaryStorage):
        self._config = config
        self._binary_storage = binary_storage

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None

    def _build_public_download_url(self, request: Request, filename: str) -> str:
        forwarded_prefix = request.headers.get("x-forwarded-prefix", "").split(",", 1)[0].strip().rstrip("/")
        if not forwarded_prefix:
            forwarded_prefix = "/api/files"
        return f"{forwarded_prefix}/download/{filename}"

    def _size_limit(self, content_type: str) -> int:
        if content_type.startswith("video/"):
            return self._config.max_video_bytes
        if content_type.startswith("image/"):
            return self._config.max_image_bytes
        return self._config.max_document_bytes

    @staticmethod
    def _asset_or_404(db: Session, asset_id: str, *, ready_only: bool = False) -> Asset:
        asset = db.get(Asset, asset_id)
        if not asset or (ready_only and asset.status != "ready"):
            raise HTTPException(status_code=404, detail="Activo no encontrado o no disponible.")
        return asset

    def health_summary(self, db: Session) -> dict[str, str | int]:
        db.execute(select(1))
        return {
            "status": "ok",
            "service": "files-service",
            "upload_dir": str(self._config.upload_dir),
            "assets": db.scalar(select(func.count()).select_from(Asset)) or 0,
            "documents": db.scalar(select(func.count()).select_from(Document)) or 0,
            "content_cards": db.scalar(select(func.count()).select_from(ContentCard)) or 0,
        }

    async def upload_file(self, db: Session, request: Request, file: UploadFile) -> Asset:
        original_name = os.path.basename(file.filename or "")
        extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        if extension not in EXTENSION_MIME_TYPES:
            raise HTTPException(status_code=422, detail="Tipo de archivo no permitido.")

        unique_filename = f"{uuid.uuid4()}.{extension}"
        file_path = self._binary_storage.resolve_path(unique_filename)
        checksum = hashlib.sha256()
        size_bytes = 0
        header = b""
        expected_type = EXTENSION_MIME_TYPES[extension]
        max_bytes = self._size_limit(expected_type)

        try:
            with file_path.open("xb") as buffer:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    if len(header) < 64:
                        header = (header + chunk)[:64]
                    size_bytes += len(chunk)
                    if size_bytes > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"El archivo supera el limite de {max_bytes} bytes.",
                        )
                    checksum.update(chunk)
                    buffer.write(chunk)

            if size_bytes == 0:
                raise HTTPException(status_code=422, detail="El archivo esta vacio.")
            detected_type = _detect_content_type(extension, header)
            if not detected_type:
                raise HTTPException(
                    status_code=422,
                    detail="La firma del archivo no corresponde a su extension.",
                )

            asset = Asset(
                id=str(uuid.uuid4()),
                filename=unique_filename,
                original_name=original_name,
                url=self._build_public_download_url(request, unique_filename),
                content_type=detected_type,
                size_bytes=size_bytes,
                checksum_sha256=checksum.hexdigest(),
                status="ready",
                is_public=True,
                created_at=self._utcnow(),
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            return asset
        except HTTPException:
            if file_path.exists():
                file_path.unlink()
            db.rollback()
            raise
        except Exception as exc:
            if file_path.exists():
                file_path.unlink()
            db.rollback()
            raise HTTPException(status_code=500, detail="Error guardando archivo.") from exc
        finally:
            await file.close()

    def list_assets(
        self,
        db: Session,
        *,
        limit: int,
        offset: int,
        search: str | None,
        content_type: str | None,
    ) -> tuple[list[Asset], int]:
        filters = [Asset.status == "ready", Asset.is_public.is_(True)]
        if search:
            needle = f"%{search.strip().lower()}%"
            filters.append(or_(
                func.lower(Asset.original_name).like(needle),
                func.lower(Asset.filename).like(needle),
            ))
        if content_type:
            normalized = content_type.strip().lower()
            if normalized.endswith("/*"):
                filters.append(Asset.content_type.like(f"{normalized[:-1]}%"))
            elif normalized in {"image", "video", "application", "text"}:
                filters.append(Asset.content_type.like(f"{normalized}/%"))
            else:
                filters.append(Asset.content_type == normalized)

        total = db.scalar(select(func.count()).select_from(Asset).where(*filters)) or 0
        assets = db.scalars(
            select(Asset)
            .where(*filters)
            .order_by(Asset.created_at.desc(), Asset.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(assets), total

    def delete_asset(self, db: Session, asset_id: str) -> None:
        asset = self._asset_or_404(db, asset_id)
        references = (
            (db.scalar(select(func.count()).select_from(Document).where(Document.asset_id == asset_id)) or 0)
            + (db.scalar(select(func.count()).select_from(ContentCard).where(ContentCard.asset_id == asset_id)) or 0)
            + (db.scalar(select(func.count()).select_from(AssetReference).where(AssetReference.asset_id == asset_id)) or 0)
        )
        if references:
            raise HTTPException(
                status_code=409,
                detail="El archivo esta siendo utilizado por contenido, configuracion u otro servicio.",
            )

        file_path = self._binary_storage.resolve_path(asset.filename)
        db.delete(asset)
        db.commit()
        if file_path.exists():
            file_path.unlink()

    def get_download(self, db: Session, filename: str) -> tuple[Asset, Path]:
        safe_name = os.path.basename(filename)
        asset = db.scalar(select(Asset).where(
            Asset.filename == safe_name,
            Asset.status == "ready",
            Asset.is_public.is_(True),
        ))
        file_path = self._binary_storage.resolve_path(safe_name)
        if not asset or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Archivo no encontrado.")
        return asset, file_path

    def list_documents(
        self,
        db: Session,
        *,
        category: str | None,
        ponente_nombre: str | None,
        session_id: str | None,
    ) -> list[Document]:
        filters = []
        if category:
            filters.append(Document.category == category)
        if ponente_nombre:
            filters.append(func.lower(Document.ponente_nombre) == ponente_nombre.strip().lower())
        if session_id:
            filters.append(Document.session_id == session_id)
        return list(db.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.sort_order.asc(), Document.created_at.asc())
        ).all())

    def create_document(self, db: Session, payload: DocumentCreate) -> Document:
        data = _model_dump(payload)
        asset_id = data.get("asset_id")
        if asset_id:
            asset = self._asset_or_404(db, asset_id, ready_only=True)
            data["file_url"] = asset.url
            data["original_name"] = data.get("original_name") or asset.original_name
        document = Document(
            id=str(uuid.uuid4()),
            **data,
            created_at=self._utcnow(),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def delete_document(self, db: Session, document_id: str) -> None:
        document = db.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado.")
        db.delete(document)
        db.commit()

    def _normalize_card(self, db: Session, payload: ContentCardCreate) -> dict:
        if payload.section not in self._config.content_sections:
            raise HTTPException(status_code=422, detail="Seccion de contenido no soportada.")
        if payload.section in {"comite", "conferencistas"}:
            raise HTTPException(
                status_code=409,
                detail="Esta seccion tiene una fuente autoritativa en Users o Agenda y es solo de lectura historica en Files.",
            )
        data = _model_dump(payload)
        data["title"] = payload.title.strip()
        data["subtitle"] = self._clean_optional(payload.subtitle)
        data["description"] = self._clean_optional(payload.description)
        asset_id = data.get("asset_id")
        if asset_id:
            asset = self._asset_or_404(db, asset_id, ready_only=True)
            if data["media_type"] == "image" and not asset.content_type.startswith("image/"):
                raise HTTPException(status_code=422, detail="El activo seleccionado no es una imagen.")
            if data["media_type"] == "video" and not asset.content_type.startswith("video/"):
                raise HTTPException(status_code=422, detail="El activo seleccionado no es un video.")
            data["image_url"] = asset.url
        return data

    def list_content_cards(self, db: Session, section: str, active_only: bool) -> list[ContentCard]:
        if section not in self._config.content_sections:
            raise HTTPException(status_code=404, detail="Seccion no encontrada.")
        filters = [ContentCard.section == section]
        if active_only:
            filters.append(ContentCard.is_active.is_(True))
        return list(db.scalars(
            select(ContentCard)
            .where(*filters)
            .order_by(ContentCard.sort_order.asc(), ContentCard.created_at.asc())
        ).all())

    def create_content_card(self, db: Session, payload: ContentCardCreate) -> ContentCard:
        timestamp = self._utcnow()
        card = ContentCard(
            id=str(uuid.uuid4()),
            **self._normalize_card(db, payload),
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(card)
        db.commit()
        db.refresh(card)
        return card

    def update_content_card(
        self,
        db: Session,
        card_id: str,
        payload: ContentCardCreate,
    ) -> ContentCard:
        card = db.get(ContentCard, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada.")
        for key, value in self._normalize_card(db, payload).items():
            setattr(card, key, value)
        card.updated_at = self._utcnow()
        db.commit()
        db.refresh(card)
        return card

    def delete_content_card(self, db: Session, card_id: str) -> None:
        card = db.get(ContentCard, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada.")
        db.delete(card)
        db.commit()

    def get_asset_internal(self, db: Session, asset_id: str) -> Asset:
        return self._asset_or_404(db, asset_id, ready_only=True)

    def claim_asset(
        self,
        db: Session,
        asset_id: str,
        owner_service: str,
        owner_type: str,
        owner_id: str,
    ) -> AssetReference:
        for value in (owner_service, owner_type):
            if not SAFE_OWNER_PART.fullmatch(value):
                raise HTTPException(status_code=422, detail="Identificador de propietario invalido.")
        if not owner_id or len(owner_id) > 255:
            raise HTTPException(status_code=422, detail="owner_id invalido.")
        self._asset_or_404(db, asset_id, ready_only=True)
        existing = db.scalar(select(AssetReference).where(
            AssetReference.asset_id == asset_id,
            AssetReference.owner_service == owner_service,
            AssetReference.owner_type == owner_type,
            AssetReference.owner_id == owner_id,
        ))
        if existing:
            return existing
        reference = AssetReference(
            asset_id=asset_id,
            owner_service=owner_service,
            owner_type=owner_type,
            owner_id=owner_id,
            created_at=self._utcnow(),
        )
        db.add(reference)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            reference = db.scalar(select(AssetReference).where(
                AssetReference.asset_id == asset_id,
                AssetReference.owner_service == owner_service,
                AssetReference.owner_type == owner_type,
                AssetReference.owner_id == owner_id,
            ))
        db.refresh(reference)
        return reference

    def release_asset(
        self,
        db: Session,
        asset_id: str,
        owner_service: str,
        owner_type: str,
        owner_id: str,
    ) -> None:
        reference = db.scalar(select(AssetReference).where(
            AssetReference.asset_id == asset_id,
            AssetReference.owner_service == owner_service,
            AssetReference.owner_type == owner_type,
            AssetReference.owner_id == owner_id,
        ))
        if reference:
            db.delete(reference)
            db.commit()

    def _ensure_default_config(self, db: Session) -> SiteConfigurationCurrent:
        current = db.get(SiteConfigurationCurrent, 1)
        if current:
            return current
        revision = SiteConfigurationRevision(
            schema_version=1,
            payload=_default_config_payload(),
            created_at=self._utcnow(),
            created_by=SYSTEM_ACTOR,
            change_summary="Configuracion inicial",
        )
        db.add(revision)
        db.flush()
        current = SiteConfigurationCurrent(id=1, current_revision=revision.revision)
        db.add(current)
        db.commit()
        db.refresh(current)
        return current

    @staticmethod
    def _revision_dict(revision: SiteConfigurationRevision, *, administrative: bool) -> dict:
        # Revisions published by the pre-Alembic prototype could contain the
        # edition label under guest_country. Agenda is the sole owner of the
        # edition/calendar contract, so never expose that legacy field again.
        payload = json.loads(json.dumps(revision.payload))
        payload.get("guest_country", {}).pop("edition_label", None)
        result = {
            **payload,
            "revision": revision.revision,
            "schema_version": revision.schema_version,
            "created_at": revision.created_at,
        }
        if administrative:
            result.update({
                "created_by": revision.created_by,
                "change_summary": revision.change_summary,
            })
        return result

    def get_site_configuration(self, db: Session) -> dict:
        current = self._ensure_default_config(db)
        revision = db.get(SiteConfigurationRevision, current.current_revision)
        return self._revision_dict(revision, administrative=False)

    def _normalize_config_assets(self, db: Session, payload: SiteConfigurationPayload) -> tuple[dict, list[str]]:
        data = _model_dump(payload)
        asset_ids = []
        branding = data["branding"]
        for prefix in ("logo", "hero"):
            asset_id = branding.get(f"{prefix}_asset_id")
            if not asset_id:
                branding[f"{prefix}_url"] = None
                continue
            asset = self._asset_or_404(db, asset_id, ready_only=True)
            if not asset.content_type.startswith("image/"):
                raise HTTPException(status_code=422, detail=f"El activo de {prefix} debe ser una imagen.")
            branding[f"{prefix}_url"] = asset.url
            asset_ids.append(asset.id)
        return data, asset_ids

    def _publish_revision(
        self,
        db: Session,
        *,
        payload: dict,
        asset_ids: list[str],
        expected_revision: int,
        actor_id: str,
        summary: str,
    ) -> dict:
        current = db.scalar(
            select(SiteConfigurationCurrent)
            .where(SiteConfigurationCurrent.id == 1)
            .with_for_update()
        ) or self._ensure_default_config(db)
        if current.current_revision != expected_revision:
            raise HTTPException(status_code=412, detail="La configuracion fue modificada por otro usuario.")
        revision = SiteConfigurationRevision(
            schema_version=1,
            payload=payload,
            created_at=self._utcnow(),
            created_by=actor_id,
            change_summary=summary.strip(),
        )
        db.add(revision)
        db.flush()
        for asset_id in set(asset_ids):
            db.add(AssetReference(
                asset_id=asset_id,
                owner_service="files-service",
                owner_type="site_config_revision",
                owner_id=str(revision.revision),
                created_at=self._utcnow(),
            ))
        current.current_revision = revision.revision
        db.commit()
        db.refresh(revision)
        return self._revision_dict(revision, administrative=False)

    def update_site_configuration(
        self,
        db: Session,
        *,
        payload: SiteConfigurationPayload,
        summary: str,
        expected_revision: int,
        actor_id: str,
    ) -> dict:
        normalized, asset_ids = self._normalize_config_assets(db, payload)
        return self._publish_revision(
            db,
            payload=normalized,
            asset_ids=asset_ids,
            expected_revision=expected_revision,
            actor_id=actor_id,
            summary=summary,
        )

    def list_site_configuration_revisions(
        self,
        db: Session,
        *,
        limit: int,
        offset: int,
    ) -> list[dict]:
        revisions = db.scalars(
            select(SiteConfigurationRevision)
            .order_by(SiteConfigurationRevision.revision.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return [self._revision_dict(item, administrative=True) for item in revisions]

    def rollback_site_configuration(
        self,
        db: Session,
        *,
        target_revision: int,
        expected_revision: int,
        actor_id: str,
        summary: str,
    ) -> dict:
        target = db.get(SiteConfigurationRevision, target_revision)
        if not target:
            raise HTTPException(status_code=404, detail="Revision no encontrada.")
        target_payload = json.loads(json.dumps(target.payload))
        target_payload.get("guest_country", {}).pop("edition_label", None)
        branding = target_payload.get("branding", {})
        asset_ids = [
            value for value in (
                branding.get("logo_asset_id"),
                branding.get("hero_asset_id"),
            ) if value
        ]
        for asset_id in asset_ids:
            self._asset_or_404(db, asset_id, ready_only=True)
        return self._publish_revision(
            db,
            payload=target_payload,
            asset_ids=asset_ids,
            expected_revision=expected_revision,
            actor_id=actor_id,
            summary=summary,
        )

    def import_legacy_metadata(self, db: Session) -> dict[str, int]:
        importer = LegacyJsonMetadataImporter(self._config, JsonRecordStore())
        return importer.import_all(db)


def build_default_files_service() -> FilesApplicationService:
    config = build_storage_config()
    return FilesApplicationService(config, LocalBinaryStorage(config.upload_dir))
