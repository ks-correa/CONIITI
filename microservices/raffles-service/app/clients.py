from collections.abc import Iterable
from typing import Any

import httpx

from .config import settings


class UpstreamServiceError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    return {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}


def fetch_attendance_snapshot(rule: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = {"session_ids", "confirmed_from", "confirmed_to", "require_registration"}
    payload = {key: value for key, value in rule.items() if key in allowed}
    payload.setdefault("require_registration", True)
    try:
        response = httpx.post(
            f"{settings.AGENDA_SERVICE_URL.rstrip('/')}/internal/attendance/eligibility-snapshot",
            headers=_headers(),
            json=payload,
            timeout=settings.UPSTREAM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise UpstreamServiceError("Agenda no pudo entregar el snapshot de asistencia.") from exc

    items = body.get("items") if isinstance(body, dict) else None
    total = body.get("total") if isinstance(body, dict) else None
    if not isinstance(items, list) or not isinstance(total, int) or isinstance(total, bool) or total != len(items):
        raise UpstreamServiceError("Agenda devolvio un contrato de elegibilidad invalido.")
    if any(not isinstance(item, dict) for item in items):
        raise UpstreamServiceError("Agenda devolvio evidencia de elegibilidad invalida.")
    return items


def fetch_profile_summaries(user_ids: Iterable[str]) -> dict[str, str]:
    ids = list(dict.fromkeys(str(user_id) for user_id in user_ids))
    if not ids:
        return {}
    result: dict[str, str] = {}
    for offset in range(0, len(ids), 200):
        batch = ids[offset : offset + 200]
        try:
            response = httpx.post(
                f"{settings.USERS_SERVICE_URL.rstrip('/')}/internal/profile-summaries",
                headers=_headers(),
                json={"user_ids": batch},
                timeout=settings.UPSTREAM_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamServiceError("Users no pudo entregar los perfiles minimos.") from exc

        items = body.get("items") if isinstance(body, dict) else None
        missing_ids = body.get("missing_ids") if isinstance(body, dict) else None
        if not isinstance(items, list) or not isinstance(missing_ids, list):
            raise UpstreamServiceError("Users devolvio un contrato de perfiles invalido.")
        returned_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict) or not item.get("id") or not item.get("full_name"):
                raise UpstreamServiceError("Users devolvio un perfil minimo invalido.")
            profile_id = str(item["id"])
            if profile_id not in batch or profile_id in returned_ids:
                raise UpstreamServiceError("Users devolvio perfiles fuera del lote solicitado.")
            returned_ids.add(profile_id)
            result[profile_id] = str(item["full_name"])
        if any(not isinstance(user_id, str) for user_id in missing_ids):
            raise UpstreamServiceError("Users devolvio missing_ids invalidos.")
        missing = set(missing_ids)
        if returned_ids & missing or returned_ids | missing != set(batch):
            raise UpstreamServiceError("Users devolvio un lote de perfiles incompleto.")
    return result
