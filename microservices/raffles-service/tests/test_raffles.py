import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


test_db_path = Path(tempfile.gettempdir()) / f"coniiti-raffles-{uuid.uuid4()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-at-least-32-characters-long"

from fastapi.testclient import TestClient  # noqa: E402

from app import clients  # noqa: E402
from app import security as security_module  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import OutboxEvent  # noqa: E402
from app.security import AuthenticatedUser, optional_current_user, require_superuser  # noqa: E402


ADMIN = AuthenticatedUser(id=str(uuid.uuid4()), role="superuser", email="admin@example.test")


def _admin():
    return ADMIN


app.dependency_overrides[require_superuser] = _admin
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[require_superuser] = _admin
    app.dependency_overrides.pop(optional_current_user, None)


def test_full_raffle_flow_is_idempotent_auditable_and_private_before_publish(monkeypatch):
    eligible_user = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    monkeypatch.setattr(
        clients,
        "fetch_attendance_snapshot",
        lambda _: [
            {
                "user_id": eligible_user,
                "session_id": session_id,
                "attendance_id": str(uuid.uuid4()),
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    monkeypatch.setattr(clients, "fetch_profile_summaries", lambda _: {eligible_user: "Persona elegible"})

    created = client.post("", json={"name": "Premio de cierre", "winner_count": 1})
    assert created.status_code == 201
    raffle_id = created.json()["id"]

    snapshot = client.post(f"/{raffle_id}/snapshot")
    assert snapshot.status_code == 200
    assert snapshot.json()["eligible_count"] == 1
    assert len(snapshot.json()["snapshot_hash"]) == 64

    app.dependency_overrides[optional_current_user] = lambda: None
    hidden = client.get(f"/{raffle_id}/result")
    assert hidden.status_code == 404
    app.dependency_overrides.pop(optional_current_user)

    key = "stable-operation-key"
    first = client.post(f"/{raffle_id}/draw", headers={"Idempotency-Key": key})
    replay = client.post(f"/{raffle_id}/draw", headers={"Idempotency-Key": key})
    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["audit_hash"] == replay.json()["audit_hash"]
    assert first.json()["user_id"] == eligible_user
    with SessionLocal() as db:
        events = db.query(OutboxEvent).all()
        assert len(events) == 1
        assert events[0].payload["winner_user_id"] == eligible_user

    published = client.post(f"/{raffle_id}/publish")
    assert published.status_code == 200
    app.dependency_overrides[optional_current_user] = lambda: None
    public_result = client.get(f"/{raffle_id}/result")
    assert public_result.status_code == 200
    winner = public_result.json()["winners"][0]
    assert "user_id" not in winner
    assert "full_name" not in winner
    assert len(winner["winner_reference"]) == 12


def test_snapshot_rejects_empty_attendance(monkeypatch):
    monkeypatch.setattr(clients, "fetch_attendance_snapshot", lambda _: [])
    created = client.post("", json={"name": "Sin candidatos"}).json()
    response = client.post(f"/{created['id']}/snapshot")
    assert response.status_code == 409


def test_snapshot_rejects_more_winners_than_eligible_people(monkeypatch):
    monkeypatch.setattr(
        clients,
        "fetch_attendance_snapshot",
        lambda _: [
            {
                "user_id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "attendance_id": str(uuid.uuid4()),
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    created = client.post("", json={"name": "Dos premios", "winner_count": 2}).json()

    response = client.post(f"/{created['id']}/snapshot")

    assert response.status_code == 409


def test_snapshot_fails_closed_for_invalid_agenda_evidence(monkeypatch):
    monkeypatch.setattr(
        clients,
        "fetch_attendance_snapshot",
        lambda _: [
            {
                "user_id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "attendance_id": "not-a-uuid",
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    created = client.post("", json={"name": "Evidencia invalida"}).json()

    response = client.post(f"/{created['id']}/snapshot")

    assert response.status_code == 503


def test_non_superuser_is_rejected():
    app.dependency_overrides[require_superuser] = lambda: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(status_code=403, detail="Se requiere rol de superusuario.")
    )
    response = client.get("")
    assert response.status_code == 403


class _IntrospectionResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_revoked_session_is_rejected_by_real_security_dependency(monkeypatch):
    app.dependency_overrides.pop(require_superuser, None)
    monkeypatch.setattr(
        security_module.httpx,
        "post",
        lambda *_, **__: _IntrospectionResponse({"active": False}),
    )

    response = client.get("/", headers={"Authorization": "Bearer revoked-token"})

    assert response.status_code == 401


def test_auth_contract_failure_is_fail_closed(monkeypatch):
    app.dependency_overrides.pop(require_superuser, None)
    monkeypatch.setattr(
        security_module.httpx,
        "post",
        lambda *_, **__: _IntrospectionResponse(["malformed"]),
    )

    response = client.get("/", headers={"Authorization": "Bearer opaque-token"})

    assert response.status_code == 503
