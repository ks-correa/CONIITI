import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["RABBITMQ_HOST"] = "rabbitmq"
os.environ["RABBITMQ_USER"] = "user"
os.environ["RABBITMQ_PASS"] = "pass"
os.environ["AUTH_INTROSPECTION_ENABLED"] = "false"
os.environ["INTERNAL_SERVICE_TOKEN"] = "internal-test-token"
os.environ["AGENDA_MEDIA_ALLOWED_HOSTS"] = "media.example.org"

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import agenda_service


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
agenda_service.publish_event = lambda routing_key, message: None
client = TestClient(app)


def setup_function():
    # Other test modules import the shared FastAPI app during collection. Restore
    # this module's database override for every test so collection order cannot
    # redirect requests to the service's default session factory.
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers(role: str = "staff", user_id: uuid.UUID | None = None) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id or uuid.uuid4()),
            "type": "access",
            "role": role,
            "email": "staff@coniiti.edu",
            "full_name": "Staff CONIITI",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "test-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def session_payload() -> dict:
    return {
        "titulo": "Pruebas de integracion en microservicios",
        "ponente": "Dra. QA DevOps",
        "track": "Desarrollo de Software",
        "event_type": "Conferencia",
        "dia": "2026-10-01",
        "hora_inicio": "09:00",
        "hora_fin": "10:00",
        "salon": "Auditorio A",
        "modalidad": "Presencial",
        "cupos_totales": 40,
    }


def test_create_session_rejects_missing_token():
    response = client.post("/", json=session_payload())

    assert response.status_code == 401


def test_create_session_rejects_non_staff_role():
    response = client.post(
        "/",
        headers=auth_headers(role="external"),
        json=session_payload(),
    )

    assert response.status_code == 403


def test_staff_can_create_update_list_and_delete_session():
    create_response = client.post(
        "/",
        headers=auth_headers(role="staff"),
        json=session_payload(),
    )

    assert create_response.status_code == 201
    session_id = create_response.json()["id"]

    list_response = client.get("/")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    update_response = client.put(
        f"/{session_id}",
        headers=auth_headers(role="superuser"),
        json={"salon": "Auditorio B"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["salon"] == "Auditorio B"

    delete_response = client.delete(f"/{session_id}", headers=auth_headers(role="superuser"))
    assert delete_response.status_code == 204
    assert client.get("/").json()["total"] == 0


def test_registration_capacity_is_enforced_and_counter_is_authoritative():
    create_response = client.post("/", headers=auth_headers(), json={**session_payload(), "cupos_totales": 1})
    session_id = create_response.json()["id"]
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()

    first = client.post(f"/{session_id}/register", headers=auth_headers("external", first_user))
    full = client.post(f"/{session_id}/register", headers=auth_headers("external", second_user))
    cancel = client.post(f"/{session_id}/register", headers=auth_headers("external", first_user))

    assert first.status_code == 200
    assert first.json() == {"registered": True, "session_id": session_id, "inscritos": 1}
    assert full.status_code == 409
    assert cancel.json()["inscritos"] == 0


def test_static_config_route_precedes_uuid_route_and_uses_etag():
    response = client.get("/config")
    assert response.status_code == 200
    assert response.headers["etag"] == '"agenda-config-v1"'
    assert "updated_by" not in response.json()

    stale = client.put(
        "/config", headers={**auth_headers("superuser"), "If-Match": '"agenda-config-v0"'},
        json={
            "edition_label": "CONIITI 2027",
            "conference_days": ["2026-10-01", "2026-10-02", "2026-10-03", "2027-09-10"],
            "timezone": "America/Bogota",
        },
    )
    assert stale.status_code == 412

    updated = client.put(
        "/config", headers={**auth_headers("superuser"), "If-Match": response.headers["etag"]},
        json={
            "edition_label": "CONIITI 2027",
            "conference_days": ["2026-10-01", "2026-10-02", "2026-10-03", "2027-09-10"],
            "timezone": "America/Bogota",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.headers["etag"] == '"agenda-config-v2"'


def test_dynamic_calendar_rejects_day_not_in_current_configuration():
    payload = session_payload()
    payload["dia"] = "2027-01-10"
    response = client.post("/", headers=auth_headers(), json=payload)
    assert response.status_code == 422


def test_attendance_event_is_retained_until_consumer_rollout_flag(monkeypatch):
    from app.models.agenda import DomainEventOutbox
    from app.services import event_outbox

    event_id = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        monkeypatch.setenv("ASISTENCIA_CONFIRMADA_ENABLED", "false")
        row = event_outbox.enqueue_event(db, "asistencia.confirmada", {
            "event_id": str(event_id),
            "event": "asistencia.confirmada",
        })
        db.commit()
        assert row is not None
        assert db.query(DomainEventOutbox).filter_by(event_id=event_id).one().status == "pending"
    finally:
        db.close()

    published = []
    monkeypatch.setattr(event_outbox, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(event_outbox, "publish_event", lambda key, payload: published.append((key, payload)))
    assert event_outbox.process_pending_events() == 0
    assert published == []

    monkeypatch.setenv("ASISTENCIA_CONFIRMADA_ENABLED", "true")
    assert event_outbox.process_pending_events() == 1
    assert published[0][0] == "asistencia.confirmada"
    with TestingSessionLocal() as verify_db:
        stored = verify_db.query(DomainEventOutbox).filter_by(event_id=event_id).one()
        assert stored.status == "done"
        assert stored.published_at is not None


def test_asset_reference_outbox_claims_and_releases_idempotent_owner(monkeypatch):
    from app.models.agenda import AssetReferenceOutbox, ResourceState, VenueResource
    from app.services import asset_reference_reconciler

    venue = client.post(
        "/venues", headers=auth_headers(),
        json={"name": "Sede Files", "capacity": 20, "is_active": True},
    ).json()
    asset_id = uuid.uuid4()
    resource_response = client.post(
        f"/venues/{venue['id']}/resources", headers=auth_headers(),
        json={
            "resource_type": "video", "title": "Video alojado",
            "alt_text": "Recorrido por la sede", "asset_id": str(asset_id),
        },
    )
    assert resource_response.status_code == 202
    resource_id = resource_response.json()["id"]
    assert resource_response.json()["state"] == "pending_asset"

    operations = []

    class FakeFilesClient:
        def lookup(self, requested_asset_id):
            assert requested_asset_id == asset_id
            return {
                "id": str(asset_id), "mime_type": "video/mp4",
                "download_url": "/api/files/download/venue.mp4",
                "is_active": True,
            }

        def claim(self, requested_asset_id, requested_resource_id):
            operations.append(("claim", requested_asset_id, requested_resource_id))
            return {}

        def release(self, requested_asset_id, requested_resource_id):
            operations.append(("release", requested_asset_id, requested_resource_id))
            return {}

    monkeypatch.setattr(asset_reference_reconciler, "SessionLocal", TestingSessionLocal)
    # SQLite can round a server-default timestamp just past the Python clock used
    # by the reconciler. Pin the retry timestamp so this integration assertion is
    # deterministic when the entire suite runs in a single process.
    with TestingSessionLocal() as db:
        pending_claim = db.query(AssetReferenceOutbox).filter_by(
            resource_id=uuid.UUID(resource_id), operation="claim",
        ).one()
        pending_claim.status = "pending"
        pending_claim.next_attempt_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()
    assert asset_reference_reconciler.process_pending_asset_references(client=FakeFilesClient()) == 1
    with TestingSessionLocal() as db:
        resource = db.query(VenueResource).filter_by(id=uuid.UUID(resource_id)).one()
        assert resource.state == ResourceState.ACTIVE.value
        assert resource.resolved_url == "/api/files/download/venue.mp4"
        assert db.query(AssetReferenceOutbox).filter_by(resource_id=resource.id).one().status == "done"

    deleted = client.delete(
        f"/venues/{venue['id']}/resources/{resource_id}", headers=auth_headers(),
    )
    assert deleted.status_code == 202
    with TestingSessionLocal() as db:
        pending_release = db.query(AssetReferenceOutbox).filter_by(
            resource_id=uuid.UUID(resource_id), operation="release",
        ).one()
        pending_release.status = "pending"
        pending_release.next_attempt_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()
    assert asset_reference_reconciler.process_pending_asset_references(client=FakeFilesClient()) == 1
    with TestingSessionLocal() as db:
        resource = db.query(VenueResource).filter_by(id=uuid.UUID(resource_id)).one()
        assert resource.state == ResourceState.TOMBSTONED.value
        assert resource.deleted_at is not None
    assert [operation[0] for operation in operations] == ["claim", "release"]


def test_video_supplemental_assets_are_resolved_before_publication(monkeypatch):
    from app.models.agenda import AssetReferenceOutbox, ResourceState, VenueResource
    from app.services import asset_reference_reconciler

    venue = client.post(
        "/venues", headers=auth_headers(),
        json={"name": "Sede Multimedia Files", "capacity": 20, "is_active": True},
    ).json()
    asset_ids = {
        "primary": uuid.uuid4(),
        "captions": uuid.uuid4(),
        "transcript": uuid.uuid4(),
    }
    response = client.post(
        f"/venues/{venue['id']}/resources", headers=auth_headers(),
        json={
            "resource_type": "video",
            "title": "Recorrido accesible",
            "alt_text": "Recorrido audiovisual por la sede",
            "asset_id": str(asset_ids["primary"]),
            "captions_asset_id": str(asset_ids["captions"]),
            "transcript_asset_id": str(asset_ids["transcript"]),
        },
    )
    assert response.status_code == 202
    resource_id = uuid.UUID(response.json()["id"])
    assert response.json()["state"] == ResourceState.PENDING_ASSET.value

    assets = {
        asset_ids["primary"]: {
            "content_type": "video/mp4",
            "download_url": "/api/files/download/venue.mp4",
            "is_active": True,
        },
        asset_ids["captions"]: {
            "content_type": "text/vtt",
            "download_url": "/api/files/download/venue.vtt",
            "is_active": True,
        },
        asset_ids["transcript"]: {
            "content_type": "text/plain",
            "download_url": "/api/files/download/venue.txt",
            "is_active": True,
        },
    }
    operations = []

    class FakeFilesClient:
        def lookup(self, asset_id):
            return assets[asset_id]

        def claim(self, asset_id, owner_id):
            operations.append(("claim", asset_id, owner_id))
            return {}

        def release(self, asset_id, owner_id):
            operations.append(("release", asset_id, owner_id))
            return {}

    monkeypatch.setattr(asset_reference_reconciler, "SessionLocal", TestingSessionLocal)
    with TestingSessionLocal() as db:
        rows = db.query(AssetReferenceOutbox).filter_by(resource_id=resource_id).all()
        assert {row.slot for row in rows} == {"primary", "captions", "transcript"}
        for row in rows:
            row.next_attempt_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()

    assert asset_reference_reconciler.process_pending_asset_references(
        client=FakeFilesClient(),
    ) == 3
    with TestingSessionLocal() as db:
        resource = db.query(VenueResource).filter_by(id=resource_id).one()
        assert resource.state == ResourceState.ACTIVE.value
        assert resource.resolved_url == "/api/files/download/venue.mp4"
        assert resource.captions_resolved_url == "/api/files/download/venue.vtt"
        assert resource.transcript_resolved_url == "/api/files/download/venue.txt"
        assert {row.status for row in db.query(AssetReferenceOutbox).all()} == {"done"}
    assert len(operations) == 3


def test_invalid_files_caption_is_dead_lettered_and_resource_stays_hidden(monkeypatch):
    from app.models.agenda import AssetReferenceOutbox, ResourceState, VenueResource
    from app.services import asset_reference_reconciler

    venue = client.post(
        "/venues", headers=auth_headers(),
        json={"name": "Sede Subtítulos", "capacity": 10, "is_active": True},
    ).json()
    captions_asset_id = uuid.uuid4()
    response = client.post(
        f"/venues/{venue['id']}/resources", headers=auth_headers(),
        json={
            "resource_type": "video",
            "title": "Video con subtítulos inválidos",
            "alt_text": "Video de prueba",
            "external_url": "https://media.example.org/video.mp4",
            "captions_asset_id": str(captions_asset_id),
        },
    )
    assert response.status_code == 202
    resource_id = uuid.UUID(response.json()["id"])

    class InvalidCaptionClient:
        def lookup(self, asset_id):
            assert asset_id == captions_asset_id
            return {
                "content_type": "text/plain",
                "download_url": "/api/files/download/not-captions.txt",
                "is_active": True,
            }

        def claim(self, asset_id, owner_id):
            raise AssertionError("Un MIME inválido no debe reclamarse.")

    monkeypatch.setattr(asset_reference_reconciler, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(asset_reference_reconciler, "MAX_ATTEMPTS", 1)
    with TestingSessionLocal() as db:
        row = db.query(AssetReferenceOutbox).filter_by(resource_id=resource_id).one()
        row.next_attempt_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()

    assert asset_reference_reconciler.process_pending_asset_references(
        client=InvalidCaptionClient(),
    ) == 0
    with TestingSessionLocal() as db:
        row = db.query(AssetReferenceOutbox).filter_by(resource_id=resource_id).one()
        resource = db.query(VenueResource).filter_by(id=resource_id).one()
        assert row.status == "dead"
        assert resource.state == ResourceState.ERROR.value
        assert resource.captions_resolved_url is None
