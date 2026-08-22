import os

os.environ["DATABASE_URL"] = "sqlite://"

from pydantic import ValidationError
import pytest

from app.models.agenda import SessionEventType, SessionModality, SessionTrack
from app.schemas.agenda import SessionCreate, SessionUpdate


def base_payload():
    return {
        "titulo": "Arquitecturas distribuidas",
        "ponente": "Dra. Ana Mesa",
        "track": SessionTrack.DESARROLLO,
        "event_type": SessionEventType.CONFERENCE,
        "dia": "2026-10-01",
        "hora_inicio": "09:00",
        "hora_fin": "10:00",
        "salon": "Auditorio A",
        "modalidad": SessionModality.PRESENCIAL,
        "cupos_totales": 40,
    }


def test_session_create_accepts_core_event_fields():
    session = SessionCreate(**base_payload())

    assert session.titulo == "Arquitecturas distribuidas"
    assert session.cupos_totales == 40


def test_session_create_requires_track():
    payload = base_payload()
    payload.pop("track")

    with pytest.raises(ValidationError):
        SessionCreate(**payload)


def test_session_schema_accepts_any_valid_date_for_service_level_calendar_validation():
    payload = base_payload()
    payload["dia"] = "2026-10-05"
    assert SessionCreate(**payload).dia == "2026-10-05"


def test_session_create_rejects_invalid_calendar_date():
    payload = base_payload()
    payload["dia"] = "2026-02-30"
    with pytest.raises(ValidationError):
        SessionCreate(**payload)


def test_session_create_rejects_invalid_time_range():
    payload = base_payload()
    payload["hora_inicio"] = "10:00"
    payload["hora_fin"] = "09:00"

    with pytest.raises(ValidationError):
        SessionCreate(**payload)


def test_session_create_rejects_negative_capacity():
    payload = base_payload()
    payload["cupos_totales"] = -1

    with pytest.raises(ValidationError):
        SessionCreate(**payload)


def test_session_update_rejects_invalid_virtual_link():
    with pytest.raises(ValidationError):
        SessionUpdate(link_virtual="javascript:alert(1)")


def test_session_update_rejects_blank_required_text():
    with pytest.raises(ValidationError):
        SessionUpdate(titulo="   ")
