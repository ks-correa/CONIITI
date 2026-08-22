import json
import logging
import threading
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from prometheus_fastapi_instrumentator import Instrumentator
from app.messaging.consumer import start_consumer
from .database import Base, SessionLocal, engine, get_db
from .models import NotificationEvent
from .security import AuthenticatedUser, require_superuser


DATABASE_READY_ATTEMPTS = 15
DATABASE_READY_DELAY_SECONDS = 2


def initialize_database() -> None:
    last_error: Exception | None = None

    for attempt in range(DATABASE_READY_ATTEMPTS):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            Base.metadata.create_all(bind=engine)
            return
        except Exception as exc:
            last_error = exc
            if attempt == DATABASE_READY_ATTEMPTS - 1:
                break
            time.sleep(DATABASE_READY_DELAY_SECONDS)

    if last_error is not None:
        raise last_error


initialize_database()

app = FastAPI(title="Notifications Service", version="1.0.0")

Instrumentator().instrument(app).expose(app)

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
            "service": "notifications-service",
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
        "service": "notifications-service",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response


@app.get("/health")
def health_check():
    db = SessionLocal()
    try:
        total_events = db.query(NotificationEvent).count()
        return {"status": "ok", "service": "notifications", "stored_events": total_events}
    except Exception:
        raise HTTPException(status_code=503, detail="Conexión con base de datos fallida")
    finally:
        db.close()


@app.get("/events")
def list_events(
    limit: int = 25,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_superuser),
):
    records = (
        db.query(NotificationEvent)
        .order_by(NotificationEvent.processed_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return {
        "total": len(records),
        "events": [
            {
                "event_id": record.event_id,
                "routing_key": record.routing_key,
                "status": record.status,
                "action_summary": record.action_summary,
                "processed_at": record.processed_at,
            }
            for record in records
        ],
    }


@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=start_consumer, daemon=True, name="notifications-consumer")
    thread.start()


@app.get("/")
def root():
    return {"message": "Notifications Service is Running"}
