import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.file_schemas import (
    AssetRead,
    AssetReferenceRead,
    ContentCardCreate,
    ContentCardRead,
    DocumentCreate,
    DocumentRead,
    SiteConfigurationRead,
    SiteConfigurationRevisionRead,
    SiteConfigurationRollback,
    SiteConfigurationUpdate,
)
from app.services.file_service import build_default_files_service
from app.utils.security import (
    AuthenticatedUser,
    require_files_manager,
    require_internal_service,
    require_superuser,
)


files_service = build_default_files_service()
logging.basicConfig(level=logging.INFO, format="%(message)s")
access_logger = logging.getLogger("coniiti.access")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("FILES_IMPORT_LEGACY_JSON", "true").lower() in {"1", "true", "yes"}:
        db = SessionLocal()
        try:
            result = files_service.import_legacy_metadata(db)
            if any(result.values()):
                access_logger.info(json.dumps({"service": "files-service", "legacy_import": result}))
        except Exception:
            db.rollback()
            access_logger.warning(
                "Legacy metadata import skipped. Apply the Files database migrations before starting the service.",
                exc_info=True,
            )
        finally:
            db.close()
    yield


app = FastAPI(title="Files Service", version="2.0.0", lifespan=lifespan)
cors_origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
cors_origins.extend(
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip() and origin.strip() not in cors_origins
)

Instrumentator().instrument(app).expose(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "X-Total-Count", "Accept-Ranges", "Content-Range"],
)

@app.middleware("http")
async def structured_access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        access_logger.exception(json.dumps({
            "service": "files-service",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
            "duration_ms": duration_ms,
            "error": str(exc),
        }))
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["x-request-id"] = request_id
    access_logger.info(json.dumps({
        "service": "files-service",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response


def _parse_if_match(value: str | None) -> int:
    if not value:
        raise HTTPException(status_code=428, detail="If-Match es obligatorio.")
    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:]
    normalized = normalized.strip('"')
    if not normalized.isdigit():
        raise HTTPException(status_code=400, detail="If-Match invalido.")
    return int(normalized)


def _parse_byte_range(value: str | None, size: int) -> tuple[int, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or (not match.group(1) and not match.group(2)):
        raise HTTPException(
            status_code=416,
            detail="Rango no satisfacible.",
            headers={"Content-Range": f"bytes */{size}"},
        )
    start_text, end_text = match.groups()
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    else:
        suffix = int(end_text)
        start = max(size - suffix, 0)
        end = size - 1
    if start >= size or start > end:
        raise HTTPException(
            status_code=416,
            detail="Rango no satisfacible.",
            headers={"Content-Range": f"bytes */{size}"},
        )
    return start, min(end, size - 1)


def _iter_file(path: Path, start: int, length: int):
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return files_service.health_summary(db)


@app.get("/")
def root():
    return {"message": "files-service running"}


@app.post("/upload", response_model=AssetRead)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    return await files_service.upload_file(db, request, file)


@app.get("/assets", response_model=list[AssetRead])
def list_assets(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=200),
    content_type: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    assets, total = files_service.list_assets(
        db,
        limit=limit,
        offset=offset,
        search=search,
        content_type=content_type,
    )
    response.headers["X-Total-Count"] = str(total)
    return assets


@app.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: str,
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    files_service.delete_asset(db, asset_id)


@app.get("/download/{filename}")
def download_file(
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
):
    asset, path = files_service.get_download(db, filename)
    byte_range = _parse_byte_range(request.headers.get("range"), asset.size_bytes)
    start, end = byte_range or (0, asset.size_bytes - 1)
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(asset.original_name)}",
        "Cache-Control": "public, max-age=3600",
        "ETag": f'"sha256-{asset.checksum_sha256}"',
        "X-Content-Type-Options": "nosniff",
    }
    status_code = 200
    if byte_range:
        headers["Content-Range"] = f"bytes {start}-{end}/{asset.size_bytes}"
        status_code = 206
    return StreamingResponse(
        _iter_file(path, start, length),
        status_code=status_code,
        media_type=asset.content_type,
        headers=headers,
    )


@app.get("/documents", response_model=list[DocumentRead])
def list_documents(
    category: str | None = Query(default=None),
    ponente_nombre: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return files_service.list_documents(
        db,
        category=category,
        ponente_nombre=ponente_nombre,
        session_id=session_id,
    )


@app.post("/documents", response_model=DocumentRead, status_code=201)
def create_document(
    payload: DocumentCreate,
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    return files_service.create_document(db, payload)


@app.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    files_service.delete_document(db, document_id)


@app.get("/content/cards/{section}", response_model=list[ContentCardRead])
def list_content_cards(
    section: str,
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return files_service.list_content_cards(db, section, active_only)


@app.post("/content/cards", response_model=ContentCardRead, status_code=201)
def create_content_card(
    payload: ContentCardCreate,
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    return files_service.create_content_card(db, payload)


@app.put("/content/cards/{card_id}", response_model=ContentCardRead)
def update_content_card(
    card_id: str,
    payload: ContentCardCreate,
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    return files_service.update_content_card(db, card_id, payload)


@app.delete("/content/cards/{card_id}", status_code=204)
def delete_content_card(
    card_id: str,
    _: AuthenticatedUser = Depends(require_files_manager),
    db: Session = Depends(get_db),
):
    files_service.delete_content_card(db, card_id)


@app.get("/site-config", response_model=SiteConfigurationRead)
def get_site_configuration(response: Response, db: Session = Depends(get_db)):
    configuration = files_service.get_site_configuration(db)
    response.headers["ETag"] = f'"{configuration["revision"]}"'
    return configuration


@app.put("/site-config", response_model=SiteConfigurationRead)
def update_site_configuration(
    payload: SiteConfigurationUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    user: AuthenticatedUser = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    configuration = files_service.update_site_configuration(
        db,
        payload=payload.configuration,
        summary=payload.change_summary,
        expected_revision=_parse_if_match(if_match),
        actor_id=user.id,
    )
    response.headers["ETag"] = f'"{configuration["revision"]}"'
    return configuration


@app.get("/site-config/revisions", response_model=list[SiteConfigurationRevisionRead])
def list_site_configuration_revisions(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: AuthenticatedUser = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return files_service.list_site_configuration_revisions(db, limit=limit, offset=offset)


@app.post("/site-config/rollback/{revision}", response_model=SiteConfigurationRead)
def rollback_site_configuration(
    revision: int,
    payload: SiteConfigurationRollback,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    user: AuthenticatedUser = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    configuration = files_service.rollback_site_configuration(
        db,
        target_revision=revision,
        expected_revision=_parse_if_match(if_match),
        actor_id=user.id,
        summary=payload.change_summary,
    )
    response.headers["ETag"] = f'"{configuration["revision"]}"'
    return configuration


@app.get(
    "/internal/assets/{asset_id}",
    response_model=AssetRead,
    dependencies=[Depends(require_internal_service)],
)
def get_asset_internal(asset_id: str, db: Session = Depends(get_db)):
    return files_service.get_asset_internal(db, asset_id)


@app.put(
    "/internal/assets/{asset_id}/references/{owner_service}/{owner_type}/{owner_id}",
    response_model=AssetReferenceRead,
    dependencies=[Depends(require_internal_service)],
)
def claim_asset_internal(
    asset_id: str,
    owner_service: str,
    owner_type: str,
    owner_id: str,
    db: Session = Depends(get_db),
):
    return files_service.claim_asset(db, asset_id, owner_service, owner_type, owner_id)


@app.delete(
    "/internal/assets/{asset_id}/references/{owner_service}/{owner_type}/{owner_id}",
    status_code=204,
    dependencies=[Depends(require_internal_service)],
)
def release_asset_internal(
    asset_id: str,
    owner_service: str,
    owner_type: str,
    owner_id: str,
    db: Session = Depends(get_db),
):
    files_service.release_asset(db, asset_id, owner_service, owner_type, owner_id)
