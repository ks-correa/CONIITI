import json
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.database import engine
from app.api import agenda, attendance, venues
from app.services.asset_reference_reconciler import start_asset_reconciler, stop_asset_reconciler
from app.services.event_outbox import start_event_outbox, stop_event_outbox


DATABASE_READY_ATTEMPTS = 15
DATABASE_READY_DELAY_SECONDS = 2


def initialize_database() -> None:
    last_error: Exception | None = None

    for attempt in range(DATABASE_READY_ATTEMPTS):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last_error = exc
            if attempt == DATABASE_READY_ATTEMPTS - 1:
                break
            time.sleep(DATABASE_READY_DELAY_SECONDS)

    if last_error is not None:
        raise last_error


initialize_database()

app = FastAPI(
    title="CONIITI Agenda Service",
    version="1.0.0",
    description="Microservicio para la gestión de sesiones, ponencias y horarios del Congreso CONIITI.",
)

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
access_logger = logging.getLogger("coniiti.access")


@app.middleware("http")
async def structured_access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        access_logger.exception(json.dumps({
            "service": "agenda-service",
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
        "service": "agenda-service",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response

@app.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": "agenda-service", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Conexión con base de datos fallida")


@app.get("/info")
def root():
    return {"message": "Welcome to Agenda Service"}


@app.on_event("startup")
def start_background_reconcilers():
    if not str(engine.url).startswith("sqlite"):
        start_asset_reconciler()
        start_event_outbox()


@app.on_event("shutdown")
def stop_background_reconcilers():
    stop_asset_reconciler()
    stop_event_outbox()


# Orden deliberado: /venues, /me y /internal deben preceder /{session_id}.
app.include_router(venues.router)
app.include_router(attendance.router)
app.include_router(agenda.router)
