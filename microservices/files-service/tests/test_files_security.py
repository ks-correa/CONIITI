import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.utils.security import AuthenticatedUser, get_current_user


client = TestClient(app)


def as_role(role: str):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=str(uuid.uuid4()),
        role=role,
        email=f"{role}@coniiti.edu",
    )


def content_card_payload() -> dict:
    return {
        "section": "memorias",
        "title": "Memorias CONIITI",
        "description": "Repositorio de memorias.",
        "is_active": True,
        "sort_order": 1,
    }


def test_content_write_requires_token():
    response = client.post("/content/cards", json=content_card_payload())
    assert response.status_code == 401


def test_content_write_rejects_non_staff_user():
    as_role("external")
    response = client.post("/content/cards", json=content_card_payload())
    assert response.status_code == 403


def test_content_write_allows_staff():
    as_role("staff")
    response = client.post("/content/cards", json=content_card_payload())
    assert response.status_code == 201
    assert response.json()["title"] == "Memorias CONIITI"


def test_site_configuration_requires_superuser():
    current = client.get("/site-config")
    as_role("staff")
    response = client.put(
        "/site-config",
        headers={"If-Match": current.headers["etag"]},
        json={
            "configuration": {
                key: value for key, value in current.json().items()
                if key not in {"revision", "schema_version", "created_at"}
            },
            "change_summary": "Cambio no autorizado",
        },
    )
    assert response.status_code == 403
