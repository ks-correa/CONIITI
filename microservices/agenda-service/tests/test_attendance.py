import uuid
from datetime import datetime, timezone

from app.services import attendance_service
from tests.test_agenda_api import auth_headers, client, session_payload


def test_signed_check_in_is_idempotent_one_use_and_eligible(monkeypatch):
    session = client.post("/", headers=auth_headers(), json=session_payload()).json()
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    client.post(f"/{session['id']}/register", headers=auth_headers("external", user_id))
    client.post(f"/{session['id']}/register", headers=auth_headers("external", other_user_id))
    monkeypatch.setattr(attendance_service, "_now", lambda: datetime(2026, 10, 1, 13, 30, tzinfo=timezone.utc))

    token_response = client.post(
        f"/{session['id']}/attendance-token",
        headers=auth_headers("staff"),
        json={"ttl_seconds": 120, "max_uses": 1},
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]

    first = client.post(
        f"/{session['id']}/attendance/check-in",
        headers=auth_headers("external", user_id), json={"token": token},
    )
    retry = client.post(
        f"/{session['id']}/attendance/check-in",
        headers=auth_headers("external", user_id), json={"token": token},
    )
    replay = client.post(
        f"/{session['id']}/attendance/check-in",
        headers=auth_headers("external", other_user_id), json={"token": token},
    )
    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert replay.status_code == 409

    snapshot = client.post(
        "/internal/attendance/eligibility-snapshot",
        headers={"X-Internal-Service-Token": "internal-test-token"},
        json={"session_ids": [session["id"]], "require_registration": True},
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["total"] == 1
    assert snapshot.json()["items"][0]["user_id"] == str(user_id)


def test_manual_attendance_and_revocation_are_audited():
    session = client.post("/", headers=auth_headers(), json=session_payload()).json()
    user_id = uuid.uuid4()
    manual = client.post(
        f"/{session['id']}/attendance/manual",
        headers=auth_headers("staff"),
        json={"user_id": str(user_id), "reason": "Documento verificado en ingreso"},
    )
    assert manual.status_code == 200
    assert manual.json()["method"] == "manual"
    assert manual.json()["confirmation_note"] == "Documento verificado en ingreso"

    revoked = client.patch(
        f"/{session['id']}/attendance/{manual.json()['id']}/revoke",
        headers=auth_headers("staff"), json={"reason": "Registro duplicado confirmado"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
