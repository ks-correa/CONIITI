from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.user_schema import ProfileCreateRequest, StaffCreateRequest, StaffUpdateRequest
from app.clients import auth_client
from app.services import profile_service


def _staff_auth_create_payload(user: StaffCreateRequest) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "email": str(user.email),
        "password": user.password,
        "full_name": user.full_name,
        "is_active": user.is_active,
    }


def _staff_profile_payload(user: StaffCreateRequest, user_id: str) -> ProfileCreateRequest:
    return ProfileCreateRequest(
        id=user_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        institution=user.institution,
        career=user.career,
        gender=user.gender,
        document=user.document,
        institutional_code=user.institutional_code,
        is_active=user.is_active,
    )


def _staff_auth_update_payload(user_data: StaffUpdateRequest) -> dict[str, Any]:
    auth_payload: dict[str, Any] = {}
    if user_data.email is not None:
        auth_payload["email"] = str(user_data.email)
    if user_data.full_name is not None:
        auth_payload["full_name"] = user_data.full_name
    if user_data.password is not None:
        auth_payload["password"] = user_data.password
    if user_data.is_active is not None:
        auth_payload["is_active"] = user_data.is_active
    return auth_payload


def create_staff_account(user: StaffCreateRequest, db: Session):
    if user.role != "staff":
        raise HTTPException(status_code=422, detail="Solo se permiten cuentas de staff.")
    if not user.password:
        raise HTTPException(status_code=422, detail="La contrasena es obligatoria para staff.")

    try:
        auth_user = auth_client.create_auth_account(_staff_auth_create_payload(user))
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", "No se pudo crear la cuenta staff.")
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="auth-service no esta disponible.") from exc

    try:
        profile_payload = _staff_profile_payload(user, auth_user["user_id"])
        return profile_service.create_profile_record(profile_payload, db)
    except HTTPException as exc:
        try:
            auth_client.delete_auth_account(auth_user["user_id"])
        except Exception as rollback_exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "Rollback fallido al eliminar cuenta auth para user %s: %s",
                auth_user.get("user_id"), rollback_exc,
            )
        raise exc


def update_staff_account(user_id: str, user_data: StaffUpdateRequest, db: Session):
    user = profile_service.get_user_or_404(user_id, db)
    if user.role != "staff":
        raise HTTPException(status_code=404, detail="Cuenta staff no encontrada.")
    if user_data.role is not None and user_data.role != "staff":
        raise HTTPException(status_code=422, detail="El endpoint de staff no permite cambiar el rol.")

    auth_payload = _staff_auth_update_payload(user_data)
    if auth_payload:
        try:
            auth_client.update_auth_account(user_id, auth_payload)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.json().get("detail", "No se pudo actualizar la cuenta staff.")
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="auth-service no esta disponible.") from exc

    return profile_service.update_profile_record(user, user_data, db)


def delete_staff_account(user_id: str, db: Session) -> None:
    user = profile_service.get_user_or_404(user_id, db)
    if user.role != "staff":
        raise HTTPException(status_code=404, detail="Cuenta staff no encontrada.")

    try:
        auth_client.delete_auth_account(user_id)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", "No se pudo eliminar la cuenta staff.")
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="auth-service no esta disponible.") from exc

    # The credential is removed before deleting the profile. If this commit
    # fails, the harmless orphan profile can be reconciled; no live credential
    # remains with stale privileges.
    profile_service.delete_profile_record(user, db)
