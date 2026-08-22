import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Asset, ContentCard, Document


@dataclass(frozen=True)
class FilesStorageConfig:
    upload_dir: Path
    data_dir: Path
    assets_store: Path
    documents_store: Path
    content_cards_store: Path
    content_sections: set[str]
    document_categories: set[str]
    max_image_bytes: int
    max_video_bytes: int
    max_document_bytes: int


def build_storage_config() -> FilesStorageConfig:
    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
    data_dir = Path(os.getenv("FILES_DATA_DIR", str(upload_dir / "_metadata")))
    upload_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    return FilesStorageConfig(
        upload_dir=upload_dir,
        data_dir=data_dir,
        assets_store=data_dir / "assets.json",
        documents_store=data_dir / "documents.json",
        content_cards_store=data_dir / "content_cards.json",
        content_sections={"memorias", "galerias", "comite", "conferencistas", "autores"},
        document_categories={"sistema", "ponente"},
        max_image_bytes=int(os.getenv("FILES_MAX_IMAGE_BYTES", str(25 * 1024 * 1024))),
        max_video_bytes=int(os.getenv("FILES_MAX_VIDEO_BYTES", os.getenv("FILES_MAX_UPLOAD_BYTES", str(512 * 1024 * 1024)))),
        max_document_bytes=int(os.getenv("FILES_MAX_DOCUMENT_BYTES", str(50 * 1024 * 1024))),
    )


class JsonRecordStore:
    def load_records(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            return []

        return data if isinstance(data, list) else []

    def save_records(self, path: Path, records: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=True, indent=2)


class LocalBinaryStorage:
    def __init__(self, upload_dir: Path):
        self._upload_dir = upload_dir

    def resolve_path(self, filename: str) -> Path:
        safe_name = os.path.basename(filename)
        return self._upload_dir / safe_name

    def delete(self, filename: str) -> None:
        target = self.resolve_path(filename)
        if target.exists():
            target.unlink()


class LegacyJsonMetadataImporter:
    """Idempotent bridge from the old JSON catalog to PostgreSQL.

    The JSON files are deliberately left untouched so an operator can compare or
    archive them after the migration. Rows with an existing identifier are skipped.
    Broken legacy asset references are preserved as URL-only metadata.
    """

    def __init__(self, config: FilesStorageConfig, record_store: JsonRecordStore):
        self._config = config
        self._record_store = record_store

    @staticmethod
    def _datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def import_all(self, db: Session) -> dict[str, int]:
        imported = {"assets": 0, "documents": 0, "content_cards": 0}

        for item in self._record_store.load_records(self._config.assets_store):
            asset_id = str(item.get("id") or "")
            if not asset_id or db.get(Asset, asset_id):
                continue
            filename = os.path.basename(str(item.get("filename") or ""))
            if not filename:
                continue
            db.add(Asset(
                id=asset_id,
                filename=filename,
                original_name=str(item.get("original_name") or filename),
                url=str(item.get("url") or f"/api/files/download/{filename}"),
                content_type=str(item.get("content_type") or "application/octet-stream"),
                size_bytes=int(item.get("size_bytes") or 0),
                checksum_sha256=str(item.get("checksum_sha256") or ("0" * 64)),
                status="ready",
                is_public=True,
                created_at=self._datetime(item.get("created_at")),
            ))
            imported["assets"] += 1
        db.flush()

        for item in self._record_store.load_records(self._config.documents_store):
            record_id = str(item.get("id") or "")
            if not record_id or db.get(Document, record_id):
                continue
            asset_id = item.get("asset_id")
            if asset_id and not db.get(Asset, str(asset_id)):
                asset_id = None
            db.add(Document(
                id=record_id,
                titulo=str(item.get("titulo") or "Documento migrado"),
                descripcion=item.get("descripcion"),
                category=item.get("category") if item.get("category") in self._config.document_categories else "sistema",
                ponente_nombre=item.get("ponente_nombre"),
                session_id=item.get("session_id"),
                file_url=str(item.get("file_url") or ""),
                asset_id=str(asset_id) if asset_id else None,
                original_name=item.get("original_name"),
                sort_order=int(item.get("sort_order") or 0),
                created_at=self._datetime(item.get("created_at")),
            ))
            imported["documents"] += 1

        for item in self._record_store.load_records(self._config.content_cards_store):
            record_id = str(item.get("id") or "")
            if not record_id or db.get(ContentCard, record_id):
                continue
            asset_id = item.get("asset_id")
            if asset_id and not db.get(Asset, str(asset_id)):
                asset_id = None
            db.add(ContentCard(
                id=record_id,
                section=str(item.get("section") or ""),
                title=str(item.get("title") or "Contenido migrado"),
                subtitle=item.get("subtitle"),
                year=item.get("year"),
                description=item.get("description"),
                image_url=item.get("image_url"),
                link_url=item.get("link_url"),
                asset_id=str(asset_id) if asset_id else None,
                media_type=str(item.get("media_type") or "image"),
                is_active=item.get("is_active", True),
                sort_order=int(item.get("sort_order") or 0),
                created_at=self._datetime(item.get("created_at")),
                updated_at=self._datetime(item.get("updated_at") or item.get("created_at")),
            ))
            imported["content_cards"] += 1

        db.commit()
        return imported
