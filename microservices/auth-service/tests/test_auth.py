import os
import sys
import types

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["GOOGLE_CLIENT_ID"] = "google-client"
os.environ["GOOGLE_CLIENT_SECRET"] = "google-secret"
os.environ["MICROSOFT_CLIENT_ID"] = "ms-client"
os.environ["MICROSOFT_CLIENT_SECRET"] = "ms-secret"


class _DummyConnection:
    def channel(self):
        return self

    def exchange_declare(self, *args, **kwargs):
        return None

    def basic_publish(self, *args, **kwargs):
        return None

    def close(self):
        return None


sys.modules.setdefault(
    "pika",
    types.SimpleNamespace(
        PlainCredentials=lambda *args, **kwargs: object(),
        ConnectionParameters=lambda *args, **kwargs: object(),
        BlockingConnection=lambda *args, **kwargs: _DummyConnection(),
        BasicProperties=lambda *args, **kwargs: object(),
    ),
)

from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import AuthUser, OTPCode, OTPPurpose
from app.clients import email_service, oauth_service, users_client
from app.messaging import event_service
from app.services import auth_service


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
client = TestClient(app)


def _publish_stub(user):
    return None


event_service.publish_user_registered = _publish_stub
users_client.create_profile = lambda **kwargs: {
    "id": kwargs["user_id"],
    "full_name": kwargs["full_name"],
    "email": kwargs["email"],
    "role": kwargs["role"],
    "institution": kwargs.get("institution"),
    "is_active": True,
}
users_client.get_profile = lambda user_id: {
    "id": user_id,
    "full_name": "Stub User",
    "email": "stub@coniiti.edu",
    "role": "external",
    "institution": None,
    "is_active": True,
}
users_client.delete_profile = lambda user_id: None
email_service.send_password_reset_email = lambda **kwargs: None


def _get_latest_otp(email: str, purpose: OTPPurpose) -> str:
    db = TestingSessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.email == email).first()
        assert user is not None
        otp = (
            db.query(OTPCode)
            .filter(OTPCode.user_id == user.id, OTPCode.purpose == purpose)
            .order_by(OTPCode.created_at.desc())
            .first()
        )
        assert otp is not None
        return otp.code
    finally:
        db.close()


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.cookies.clear()
    email_service.send_password_reset_email = lambda **kwargs: None


def test_register_success():
    response = client.post(
        "/register",
        json={
            "email": "demo@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Demo User",
            "role": "external",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "demo@coniiti.edu"
    assert data["full_name"] == "Demo User"
    assert data["user_id"]
    assert data["requires_otp"] is True
    assert data["purpose"] == "register"


def test_register_rolls_back_when_otp_email_fails():
    def _raise_otp_failure(**kwargs):
        raise HTTPException(status_code=503, detail="No fue posible enviar el codigo de verificacion.")

    original_send_otp_email = email_service.send_otp_email
    email_service.send_otp_email = _raise_otp_failure

    try:
        response = client.post(
            "/register",
            json={
                "email": "rollback@coniiti.edu",
                "password": "ClaveSegura123",
                "full_name": "Rollback User",
                "role": "external",
            },
        )
    finally:
        email_service.send_otp_email = original_send_otp_email

    assert response.status_code == 503
    assert response.json()["detail"] == "No fue posible enviar el codigo de verificacion."

    db = TestingSessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.email == "rollback@coniiti.edu").first()
        otp_codes = db.query(OTPCode).all()
        assert user is None
        assert otp_codes == []
    finally:
        db.close()


def test_login_success():
    client.post(
        "/register",
        json={
            "email": "login@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Login User",
            "role": "external",
        },
    )
    verify_response = client.post(
        "/verify-otp",
        json={
            "email": "login@coniiti.edu",
            "code": _get_latest_otp("login@coniiti.edu", OTPPurpose.REGISTER),
            "purpose": "register",
        },
    )
    assert verify_response.status_code == 200
    client.post("/logout")

    response = client.post(
        "/login",
        json={
            "email": "login@coniiti.edu",
            "password": "ClaveSegura123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_otp"] is False
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["role"] == "external"


def test_login_requires_otp_for_unverified_user():
    client.post(
        "/register",
        json={
            "email": "otp-login@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "OTP Login User",
            "role": "external",
        },
    )

    response = client.post(
        "/login",
        json={
            "email": "otp-login@coniiti.edu",
            "password": "ClaveSegura123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_otp"] is True
    assert data["purpose"] == "login"
    assert data["email"] == "otp-login@coniiti.edu"


def test_login_requires_otp_for_staff_accounts():
    create_response = client.post(
        "/internal/users",
        headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        json={
            "email": "staff@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Staff User",
            "is_active": True,
        },
    )

    assert create_response.status_code == 201
    user_id = create_response.json()["user_id"]
    original_get_profile = users_client.get_profile
    users_client.get_profile = lambda requested_user_id: {
        "id": requested_user_id,
        "full_name": "Staff User",
        "email": "staff@coniiti.edu",
        "role": "staff" if requested_user_id == user_id else "external",
        "institution": None,
        "is_active": True,
    }

    try:
        response = client.post(
            "/login",
            json={
                "email": "staff@coniiti.edu",
                "password": "ClaveSegura123",
            },
        )
    finally:
        users_client.get_profile = original_get_profile

    assert response.status_code == 200
    data = response.json()
    assert data["requires_otp"] is True
    assert data["purpose"] == "login"
    assert data["role"] == "staff"


def test_verify_otp_starts_session_after_register():
    client.post(
        "/register",
        json={
            "email": "verify@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Verify User",
            "role": "external",
        },
    )

    response = client.post(
        "/verify-otp",
        json={
            "email": "verify@coniiti.edu",
            "code": _get_latest_otp("verify@coniiti.edu", OTPPurpose.REGISTER),
            "purpose": "register",
        },
    )

    assert response.status_code == 200
    assert "access_token=" in response.headers["set-cookie"]

    me_response = client.get("/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "verify@coniiti.edu"
    assert me_response.json()["is_verified"] is True


def test_login_failure_with_invalid_password():
    client.post(
        "/register",
        json={
            "email": "fail@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Fail User",
            "role": "external",
        },
    )

    response = client.post(
        "/login",
        json={
            "email": "fail@coniiti.edu",
            "password": "incorrecta123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "La contrasena es incorrecta."


def test_login_failure_with_unknown_email():
    response = client.post(
        "/login",
        json={
            "email": "unknown@coniiti.edu",
            "password": "ClaveSegura123",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No existe una cuenta registrada con ese correo."


def test_forgot_and_reset_password_flow():
    captured = {}

    def _capture_reset_email(**kwargs):
        captured["reset_url"] = kwargs["reset_url"]

    email_service.send_password_reset_email = _capture_reset_email

    client.post(
        "/register",
        json={
            "email": "reset@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Reset User",
            "role": "external",
        },
    )
    verify_response = client.post(
        "/verify-otp",
        json={
            "email": "reset@coniiti.edu",
            "code": _get_latest_otp("reset@coniiti.edu", OTPPurpose.REGISTER),
            "purpose": "register",
        },
    )
    assert verify_response.status_code == 200
    client.post("/logout")

    forgot_response = client.post(
        "/forgot-password",
        json={"email": "reset@coniiti.edu"},
    )

    assert forgot_response.status_code == 200
    assert "reset_url" in captured

    parsed = urlparse(captured["reset_url"])
    token = parse_qs(parsed.query)["token"][0]

    reset_response = client.post(
        "/reset-password",
        json={
            "token": token,
            "new_password": "NuevaClave456",
        },
    )

    assert reset_response.status_code == 200

    old_login = client.post(
        "/login",
        json={"email": "reset@coniiti.edu", "password": "ClaveSegura123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/login",
        json={"email": "reset@coniiti.edu", "password": "NuevaClave456"},
    )
    assert new_login.status_code == 200


def test_google_oauth_redirect_sets_state_cookie():
    response = client.get(
        "/oauth/google",
        headers={
            "x-forwarded-prefix": "/api/auth",
            "x-forwarded-host": "localhost",
            "x-forwarded-proto": "http",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    params = parse_qs(urlparse(location).query)

    assert "accounts.google.com" in location
    assert "oauth_state=" in response.headers["set-cookie"]
    assert params["client_id"] == ["google-client"]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == ["http://localhost/api/auth/oauth/google/callback"]
    assert params["scope"] == ["openid email profile"]
    assert params["prompt"] == ["select_account"]
    assert params["access_type"] == ["offline"]


def test_oauth_ignores_untrusted_frontend_origin():
    response = client.get(
        "/oauth/google",
        headers={
            "origin": "https://attacker.example",
            "referer": "https://attacker.example/phishing",
            "x-forwarded-prefix": "/api/auth",
            "x-forwarded-host": "attacker.example",
            "x-forwarded-proto": "https",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "frontend_origin=" not in response.headers.get("set-cookie", "")
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["redirect_uri"] == [settings.GOOGLE_REDIRECT_URI]


def test_google_oauth_callback_creates_session_cookie():
    async def _exchange_google_code(_code, redirect_uri=None):
        assert redirect_uri == "http://localhost/api/auth/oauth/google/callback"
        return {
            "email": "oauth@coniiti.edu",
            "full_name": "OAuth User",
        }

    oauth_service.exchange_google_code = _exchange_google_code
    users_client.create_profile = lambda **kwargs: {
        "id": kwargs["user_id"],
        "full_name": kwargs["full_name"],
        "email": kwargs["email"],
        "role": kwargs["role"],
        "institution": kwargs.get("institution"),
        "is_active": True,
    }
    users_client.get_profile = lambda user_id: {
        "id": user_id,
        "full_name": "OAuth User",
        "email": "oauth@coniiti.edu",
        "role": "external",
        "institution": None,
        "is_active": True,
    }

    forwarded_headers = {
        "x-forwarded-prefix": "/api/auth",
        "x-forwarded-host": "localhost",
        "x-forwarded-proto": "http",
    }
    start_response = client.get("/oauth/google", headers=forwarded_headers, follow_redirects=False)
    state = parse_qs(urlparse(start_response.headers["location"]).query)["state"][0]

    callback_response = client.get(
        f"/oauth/google/callback?code=test-code&state={state}",
        headers=forwarded_headers,
        follow_redirects=False,
    )

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == f"{settings.FRONTEND_URL}/login?oauth=success"
    assert "access_token=" in callback_response.headers["set-cookie"]

    me_response = client.get("/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "oauth@coniiti.edu"


def test_microsoft_oauth_callback_creates_session_cookie():
    async def _exchange_microsoft_code(_code, redirect_uri=None):
        assert redirect_uri == "http://localhost/api/auth/oauth/microsoft/callback"
        return {
            "email": "microsoft@coniiti.edu",
            "full_name": "Microsoft User",
        }

    oauth_service.exchange_microsoft_code = _exchange_microsoft_code
    users_client.create_profile = lambda **kwargs: {
        "id": kwargs["user_id"],
        "full_name": kwargs["full_name"],
        "email": kwargs["email"],
        "role": kwargs["role"],
        "institution": kwargs.get("institution"),
        "is_active": True,
    }
    users_client.get_profile = lambda user_id: {
        "id": user_id,
        "full_name": "Microsoft User",
        "email": "microsoft@coniiti.edu",
        "role": "external",
        "institution": None,
        "is_active": True,
    }

    forwarded_headers = {
        "x-forwarded-prefix": "/api/auth",
        "x-forwarded-host": "localhost",
        "x-forwarded-proto": "http",
    }
    start_response = client.get("/oauth/microsoft", headers=forwarded_headers, follow_redirects=False)
    state = parse_qs(urlparse(start_response.headers["location"]).query)["state"][0]

    callback_response = client.get(
        f"/oauth/microsoft/callback?code=test-code&state={state}",
        headers=forwarded_headers,
        follow_redirects=False,
    )

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == f"{settings.FRONTEND_URL}/login?oauth=success"
    assert "access_token=" in callback_response.headers["set-cookie"]

    me_response = client.get("/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "microsoft@coniiti.edu"


def test_microsoft_oauth_redirect_includes_select_account():
    response = client.get(
        "/oauth/microsoft",
        headers={
            "x-forwarded-prefix": "/api/auth",
            "x-forwarded-host": "localhost",
            "x-forwarded-proto": "http",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    params = parse_qs(urlparse(location).query)

    assert "login.microsoftonline.com" in location
    assert params["client_id"] == ["ms-client"]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == ["http://localhost/api/auth/oauth/microsoft/callback"]
    assert params["scope"] == ["openid email profile User.Read"]
    assert params["prompt"] == ["select_account"]


def test_internal_introspection_rejects_token_after_session_revocation():
    create_response = client.post(
        "/internal/users",
        headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        json={
            "email": "revocable@coniiti.edu",
            "password": "ClaveSegura123",
            "full_name": "Revocable User",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["user_id"]

    db = TestingSessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.id == user_id).one()
        token = auth_service.create_access_token_for_user(user, "external", user.full_name)
        original_version = user.session_version
    finally:
        db.close()

    introspection = client.post(
        "/internal/introspect",
        headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        json={"token": token},
    )
    assert introspection.status_code == 200
    assert introspection.json()["active"] is True
    assert introspection.json()["session_version"] == original_version

    revoked = client.post(
        f"/internal/users/{user_id}/revoke-sessions",
        headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        json={},
    )
    assert revoked.status_code == 200
    assert revoked.json()["session_version"] == original_version + 1

    stale = client.post(
        "/internal/introspect",
        headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        json={"token": token},
    )
    assert stale.status_code == 200
    assert stale.json() == {
        "active": False,
        "user_id": None,
        "email": None,
        "full_name": None,
        "role": None,
        "session_version": None,
        "expires_at": None,
    }
