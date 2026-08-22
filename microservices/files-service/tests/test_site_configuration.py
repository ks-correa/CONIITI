import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.utils.security import AuthenticatedUser, get_current_user


client = TestClient(app)


def as_superuser():
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=str(uuid.uuid4()), role="superuser", email="root@coniiti.edu",
    )


def writable(configuration):
    return {
        key: value for key, value in configuration.items()
        if key not in {"revision", "schema_version", "created_at"}
    }


def test_configuration_uses_etag_history_and_rollback():
    current = client.get("/site-config")
    assert current.status_code == 200
    assert current.headers["etag"] == '"1"'
    payload = writable(current.json())
    payload["pages"]["home"]["title"] = "CONIITI global"

    as_superuser()
    saved = client.put(
        "/site-config",
        headers={"If-Match": current.headers["etag"]},
        json={"configuration": payload, "change_summary": "Nuevo titulo global"},
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2
    assert saved.headers["etag"] == '"2"'

    stale = client.put(
        "/site-config",
        headers={"If-Match": '"1"'},
        json={"configuration": payload, "change_summary": "Edicion obsoleta"},
    )
    assert stale.status_code == 412

    history = client.get("/site-config/revisions")
    assert [item["revision"] for item in history.json()] == [2, 1]
    assert "created_by" in history.json()[0]
    assert "created_by" not in client.get("/site-config").json()

    rolled_back = client.post(
        "/site-config/rollback/1",
        headers={"If-Match": '"2"'},
        json={"change_summary": "Restaurar configuracion inicial"},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["revision"] == 3
    assert rolled_back.json()["pages"]["home"]["title"] == "XI CONIITI 2026"


def test_configuration_rejects_invalid_color_and_missing_if_match():
    current = client.get("/site-config").json()
    payload = writable(current)
    payload["guest_country"]["colors"] = ["red", "#ffffff", "#000000"]
    as_superuser()
    assert client.put(
        "/site-config",
        headers={"If-Match": '"1"'},
        json={"configuration": payload, "change_summary": "Color invalido"},
    ).status_code == 422
    payload["guest_country"]["colors"] = ["#000000", "#ffffff", "#123456"]
    assert client.put(
        "/site-config",
        json={"configuration": payload, "change_summary": "Sin control de concurrencia"},
    ).status_code == 428
