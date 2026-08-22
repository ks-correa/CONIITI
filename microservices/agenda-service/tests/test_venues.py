from tests.test_agenda_api import auth_headers, client, session_payload


def venue_payload(name="Auditorio Central", capacity=80):
    return {"name": name, "description": "Sede principal CES", "capacity": capacity, "is_active": True}


def test_venues_static_route_rbac_resources_and_session_filter():
    assert client.post("/venues", json=venue_payload()).status_code == 401
    created = client.post("/venues", headers=auth_headers(), json=venue_payload())
    assert created.status_code == 201
    venue_id = created.json()["id"]

    resource = client.post(
        f"/venues/{venue_id}/resources",
        headers=auth_headers(),
        json={
            "resource_type": "video",
            "title": "Recorrido CES",
            "alt_text": "Recorrido audiovisual por la sede CES",
            "external_url": "https://media.example.org/ces.mp4",
            "mime_type": "video/mp4",
            "display_order": 1,
        },
    )
    assert resource.status_code == 202
    assert resource.json()["state"] == "active"

    payload = session_payload()
    payload.pop("salon")
    payload["venue_id"] = venue_id
    session = client.post("/", headers=auth_headers(), json=payload)
    assert session.status_code == 201
    assert session.json()["salon"] == "Auditorio Central"
    assert session.json()["venue"]["resources"][0]["title"] == "Recorrido CES"

    filtered = client.get(f"/?venue_id={venue_id}")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert client.get("/venues").status_code == 200


def test_venue_capacity_overlap_and_historical_delete_guards():
    venue = client.post("/venues", headers=auth_headers(), json=venue_payload("Sala Pequeña", 10)).json()
    too_large = {**session_payload(), "venue_id": venue["id"], "salon": None, "cupos_totales": 11}
    assert client.post("/", headers=auth_headers(), json=too_large).status_code == 422

    first = {**session_payload(), "venue_id": venue["id"], "salon": None, "cupos_totales": 10}
    assert client.post("/", headers=auth_headers(), json=first).status_code == 201
    overlap = {**first, "titulo": "Sesión simultánea", "ponente": "Otro ponente"}
    assert client.post("/", headers=auth_headers(), json=overlap).status_code == 409
    assert client.delete(f"/venues/{venue['id']}", headers=auth_headers()).status_code == 409


def test_visual_resource_requires_alt_text_and_exactly_one_source():
    venue = client.post("/venues", headers=auth_headers(), json=venue_payload("Sala Multimedia", 20)).json()
    response = client.post(
        f"/venues/{venue['id']}/resources",
        headers=auth_headers(),
        json={"resource_type": "video", "title": "Video", "external_url": "https://example.org/v.mp4"},
    )
    assert response.status_code == 422

    supplemental_on_image = client.post(
        f"/venues/{venue['id']}/resources",
        headers=auth_headers(),
        json={
            "resource_type": "image",
            "title": "Plano",
            "alt_text": "Plano de la sede",
            "external_url": "https://media.example.org/plano.png",
            "captions_url": "https://media.example.org/plano.vtt",
        },
    )
    assert supplemental_on_image.status_code == 422
