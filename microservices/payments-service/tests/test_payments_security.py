import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ["PAYMENTS_DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["PAYMENT_PROVIDER_MODE"] = "mock"
os.environ.pop("AUTH_SERVICE_URL", None)
os.environ.pop("INTERNAL_SERVICE_TOKEN", None)

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import payments as payments_api
from app.database import Base, get_db
from app.main import app
from app.services.payment_service import PaymentApplicationService
from app.utils import security


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


class FakeGatewayResolver:
    async def create_checkout(self, payment, request):
        return SimpleNamespace(
            provider_reference_id=f"fake-{payment.id}",
            checkout_url=f"http://localhost/api/payments/mock-checkout/{payment.id}",
        )


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
payments_api.payment_service = PaymentApplicationService(FakeGatewayResolver())
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers(user_id: uuid.UUID, role: str = "external") -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "role": role,
            "email": "payer@coniiti.edu",
            "full_name": "Payer User",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "test-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def payment_payload(user_id: uuid.UUID) -> dict:
    return {
        "user_id": str(user_id),
        "amount": 120000,
        "currency": "COP",
        "payment_region": "LOCAL",
    }


def test_create_checkout_requires_token():
    response = client.post("/create-checkout", json=payment_payload(uuid.uuid4()))

    assert response.status_code == 401


def test_external_user_cannot_create_checkout_for_another_user():
    current_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    response = client.post(
        "/create-checkout",
        headers=auth_headers(current_user_id),
        json=payment_payload(other_user_id),
    )

    assert response.status_code == 403


def test_external_user_can_create_checkout_for_self():
    current_user_id = uuid.uuid4()

    response = client.post(
        "/create-checkout",
        headers=auth_headers(current_user_id),
        json=payment_payload(current_user_id),
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(current_user_id)


def test_superuser_can_create_checkout_for_another_user():
    current_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    response = client.post(
        "/create-checkout",
        headers=auth_headers(current_user_id, role="superuser"),
        json=payment_payload(other_user_id),
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(other_user_id)


class _IntrospectionResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_deployed_security_uses_revocation_aware_introspection(monkeypatch):
    current_user_id = uuid.uuid4()
    monkeypatch.setattr(security, "AUTH_SERVICE_URL", "http://auth-service")
    monkeypatch.setattr(security, "INTERNAL_SERVICE_TOKEN", "internal-test-token")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *_, **__: _IntrospectionResponse(
            {
                "active": True,
                "user_id": str(current_user_id),
                "role": "SUPERUSER",
            }
        ),
    )

    response = client.post(
        "/create-checkout",
        headers={"Authorization": "Bearer opaque-session-token"},
        json=payment_payload(uuid.uuid4()),
    )

    assert response.status_code == 201


def test_deployed_security_rejects_revoked_session(monkeypatch):
    monkeypatch.setattr(security, "AUTH_SERVICE_URL", "http://auth-service")
    monkeypatch.setattr(security, "INTERNAL_SERVICE_TOKEN", "internal-test-token")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *_, **__: _IntrospectionResponse({"active": False}),
    )

    response = client.post(
        "/create-checkout",
        headers={"Authorization": "Bearer revoked-session-token"},
        json=payment_payload(uuid.uuid4()),
    )

    assert response.status_code == 401


def test_deployed_security_fails_closed_for_malformed_introspection(monkeypatch):
    monkeypatch.setattr(security, "AUTH_SERVICE_URL", "http://auth-service")
    monkeypatch.setattr(security, "INTERNAL_SERVICE_TOKEN", "internal-test-token")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *_, **__: _IntrospectionResponse(["invalid-contract"]),
    )

    response = client.post(
        "/create-checkout",
        headers={"Authorization": "Bearer opaque-session-token"},
        json=payment_payload(uuid.uuid4()),
    )

    assert response.status_code == 503


def test_deployed_security_fails_closed_for_invalid_active_subject(monkeypatch):
    monkeypatch.setattr(security, "AUTH_SERVICE_URL", "http://auth-service")
    monkeypatch.setattr(security, "INTERNAL_SERVICE_TOKEN", "internal-test-token")
    monkeypatch.setattr(
        security.httpx,
        "post",
        lambda *_, **__: _IntrospectionResponse(
            {"active": True, "user_id": "not-a-uuid", "role": "superuser"}
        ),
    )

    response = client.post(
        "/create-checkout",
        headers={"Authorization": "Bearer opaque-session-token"},
        json=payment_payload(uuid.uuid4()),
    )

    assert response.status_code == 503
