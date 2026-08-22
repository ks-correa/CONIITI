import pytest

from app.services import InvalidPayloadError, process_event


def test_process_user_registered_event_builds_welcome_summary():
    summary = process_event(
        "usuario.registrado",
        {
            "event_id": "evt-001",
            "email": "ada@coniiti.edu",
            "name": "Ada Lovelace",
        },
    )

    assert "Ada Lovelace" in summary
    assert "ada@coniiti.edu" in summary


def test_process_agenda_update_requires_non_empty_changes():
    with pytest.raises(InvalidPayloadError):
        process_event(
            "agenda.sesion_actualizada",
            {
                "event_id": "evt-002",
                "titulo": "Arquitectura distribuida",
                "cambios": {},
                "afectados": ["user-1"],
            },
        )


def test_process_event_rejects_unsupported_routing_key():
    with pytest.raises(InvalidPayloadError):
        process_event("desconocido", {"event_id": "evt-003"})


def test_process_attendance_event_without_exposing_identity():
    summary = process_event(
        "asistencia.confirmada",
        {
            "event_id": "evt-attendance",
            "event": "asistencia.confirmada",
            "session_id": "session-1",
            "user_id": "user-sensitive-id",
            "confirmed_at": "2026-08-21T10:00:00Z",
        },
    )
    assert "user-sensitive-id" not in summary


def test_process_prize_event_is_supported_and_minimized():
    summary = process_event(
        "premio.adjudicado",
        {
            "event_id": "evt-prize",
            "event": "premio.adjudicado",
            "raffle_id": "raffle-1",
            "winner_user_id": "winner-sensitive-id",
            "draw_number": 1,
            "drawn_at": "2026-08-21T10:00:00Z",
            "audit_hash": "a" * 64,
        },
    )
    assert "winner-sensitive-id" not in summary


def test_process_event_rejects_mismatched_envelope_type():
    with pytest.raises(InvalidPayloadError):
        process_event(
            "premio.adjudicado",
            {
                "event_id": "evt-mismatch",
                "event": "asistencia.confirmada",
            },
        )


def test_process_event_rejects_oversized_event_id():
    with pytest.raises(InvalidPayloadError):
        process_event("usuario.registrado", {"event_id": "x" * 65})
