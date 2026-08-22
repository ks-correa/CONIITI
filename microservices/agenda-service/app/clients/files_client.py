import os
import uuid
from urllib.parse import quote

import httpx


class FilesIntegrationError(RuntimeError):
    pass


class FilesClient:
    def __init__(self):
        self.base_url = os.getenv("FILES_SERVICE_URL", "http://files-service:8000").rstrip("/")
        self.token = os.getenv("INTERNAL_SERVICE_TOKEN")
        self.timeout = float(os.getenv("FILES_SERVICE_TIMEOUT_SECONDS", "4"))

    @property
    def headers(self):
        if not self.token:
            raise FilesIntegrationError("INTERNAL_SERVICE_TOKEN no está configurado.")
        return {"X-Internal-Service-Token": self.token}

    def _request(self, method: str, path: str) -> dict:
        try:
            response = httpx.request(
                method, f"{self.base_url}{path}", headers=self.headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise FilesIntegrationError(f"Files no disponible: {exc}") from exc
        if response.status_code >= 400:
            raise FilesIntegrationError(
                f"Files respondió {response.status_code}: {response.text[:300]}",
            )
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise FilesIntegrationError("Files devolvió una respuesta no JSON.") from exc

    def lookup(self, asset_id: uuid.UUID) -> dict:
        return self._request("GET", f"/internal/assets/{asset_id}")

    def claim(self, asset_id: uuid.UUID, resource_id: uuid.UUID) -> dict:
        return self._request(
            "PUT",
            f"/internal/assets/{asset_id}/references/agenda-service/venue_resource/{resource_id}",
        )

    def release(self, asset_id: uuid.UUID, resource_id: uuid.UUID) -> dict:
        return self._request(
            "DELETE",
            f"/internal/assets/{asset_id}/references/agenda-service/venue_resource/{resource_id}",
        )


def public_asset_url(asset: dict) -> str:
    direct = asset.get("download_url") or asset.get("url") or asset.get("public_url")
    if direct:
        return str(direct)
    filename = asset.get("filename") or asset.get("stored_filename")
    if filename:
        return f"/api/files/download/{quote(str(filename))}"
    raise FilesIntegrationError("El lookup del asset no incluyó una URL de descarga.")


def validate_asset_type(resource_type: str, asset: dict) -> str:
    mime_type = str(asset.get("mime_type") or asset.get("content_type") or "").lower()
    if not mime_type:
        raise FilesIntegrationError("El asset no tiene MIME validado.")
    allowed = {
        "video": ("video/",),
        "image": ("image/",),
        "poster": ("image/",),
        "document": ("application/", "text/"),
    }.get(resource_type, ())
    if allowed and not mime_type.startswith(allowed):
        raise FilesIntegrationError(
            f"MIME {mime_type} incompatible con recurso {resource_type}.",
        )
    if asset.get("is_active") is False or asset.get("deleted_at"):
        raise FilesIntegrationError("El asset no está activo.")
    return mime_type
