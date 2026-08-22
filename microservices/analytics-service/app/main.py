import asyncio
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.middleware.cors import CORSMiddleware

from app.database import database, events_collection
from app.messaging.consumer import start_consumer
from app.security import AuthenticatedUser, require_superuser


app = FastAPI(title="Analytics Service", version="1.0.0")

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
            "service": "analytics-service",
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
        "service": "analytics-service",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response


@app.on_event("startup")
async def startup_event():
    await events_collection.create_index(
        "event_id",
        name="uq_analytics_event_id",
        unique=True,
        partialFilterExpression={"event_id": {"$type": "string"}},
    )
    asyncio.create_task(start_consumer())


@app.get("/health")
async def health_check():
    try:
        await database.command("ping")
        return {"status": "ok", "service": "analytics-service", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Conexión con base de datos fallida")


@app.get("/")
def root():
    return {"message": "analytics-service running"}


@app.get("/stats")
async def get_stats(_: AuthenticatedUser = Depends(require_superuser)):
    total_events = await events_collection.count_documents({})
    pipeline = [{"$group": {"_id": "$event", "count": {"$sum": 1}}}]
    cursor = events_collection.aggregate(pipeline)
    by_type = await cursor.to_list(length=100)

    return {
        "total_events_logged": total_events,
        "breakdown_by_type": by_type,
    }
