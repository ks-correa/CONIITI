import io
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.utils.security import AuthenticatedUser, get_current_user


client = TestClient(app)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"safe-png-content"
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + (b"video-data" * 20)


def as_manager(role="staff"):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=str(uuid.uuid4()), role=role, email="manager@coniiti.edu",
    )


def upload(name="foto.png", content=PNG_BYTES, content_type="image/png"):
    as_manager()
    return client.post("/upload", files={"file": (name, io.BytesIO(content), content_type)})


def test_upload_validates_signature_and_supports_search():
    invalid = upload(content=b"not-a-png")
    assert invalid.status_code == 422

    uploaded = upload()
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["status"] == "ready"
    assert body["mime_type"] == "image/png"
    assert body["download_url"] == body["url"]

    found = client.get("/assets", params={"search": "foto", "content_type": "image"})
    assert found.status_code == 200
    assert found.headers["x-total-count"] == "1"
    assert found.json()[0]["id"] == body["id"]


def test_video_stream_honors_http_range():
    uploaded = upload("ces.mp4", MP4_BYTES, "video/mp4")
    assert uploaded.status_code == 200
    streamed = client.get(uploaded.json()["url"].replace("/api/files", ""), headers={"Range": "bytes=4-15"})
    assert streamed.status_code == 206
    assert streamed.headers["accept-ranges"] == "bytes"
    assert streamed.headers["content-range"] == f"bytes 4-15/{len(MP4_BYTES)}"
    assert streamed.headers["x-content-type-options"] == "nosniff"
    assert streamed.content == MP4_BYTES[4:16]


def test_webvtt_caption_upload_validates_signature():
    invalid = upload("captions.vtt", b"not-webvtt", "text/vtt")
    assert invalid.status_code == 422

    uploaded = upload(
        "captions.vtt",
        b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nBienvenidos a CONIITI.\n",
        "text/vtt",
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["content_type"] == "text/vtt"


def test_gallery_asset_reference_blocks_delete():
    asset = upload().json()
    card = client.post("/content/cards", json={
        "section": "galerias",
        "title": "Galeria persistida",
        "asset_id": asset["id"],
        "media_type": "image",
    })
    assert card.status_code == 201
    assert card.json()["image_url"] == asset["url"]
    blocked = client.delete(f"/assets/{asset['id']}")
    assert blocked.status_code == 409


def test_internal_claim_is_idempotent_and_release_allows_delete():
    asset = upload().json()
    path = f"/internal/assets/{asset['id']}/references/agenda-service/venue_resource/resource-1"
    headers = {"X-Internal-Service-Token": "test-internal-token"}
    lookup = client.get(f"/internal/assets/{asset['id']}", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["download_url"] == asset["url"]

    first = client.put(path, headers=headers)
    second = client.put(path, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert client.delete(f"/assets/{asset['id']}").status_code == 409
    assert client.delete(path, headers=headers).status_code == 204
    assert client.delete(f"/assets/{asset['id']}").status_code == 204


def test_internal_routes_reject_browser_credentials():
    asset = upload().json()
    as_manager("superuser")
    assert client.get(f"/internal/assets/{asset['id']}").status_code == 401
