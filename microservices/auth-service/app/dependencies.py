import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal_request(
    x_internal_service_token: str | None = Header(default=None),
) -> None:
    if not x_internal_service_token or not secrets.compare_digest(
        x_internal_service_token,
        settings.INTERNAL_SERVICE_TOKEN,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solicitud interna no autorizada.",
        )
