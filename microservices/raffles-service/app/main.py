import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from .api import router
from .database import SessionLocal
from .messaging import start_outbox_worker


stop_outbox = threading.Event()


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_outbox.clear()
    worker = start_outbox_worker(stop_outbox)
    yield
    stop_outbox.set()
    worker.join(timeout=2)


app = FastAPI(
    title="CONIITI Raffles Service",
    version="1.0.0",
    description="Sorteos auditables basados en asistencia confirmada.",
    lifespan=lifespan,
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
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
        access_logger.exception(
            json.dumps(
                {
                    "service": "raffles-service",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                }
            )
        )
        raise
    response.headers["x-request-id"] = request_id
    access_logger.info(
        json.dumps(
            {
                "service": "raffles-service",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            }
        )
    )
    return response


@app.get("/health")
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "raffles-service", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Conexion con base de datos fallida.") from exc
    finally:
        db.close()


app.include_router(router)
