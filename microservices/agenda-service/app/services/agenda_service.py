import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.messaging.rabbitmq import publish_event
from app.models.agenda import AgendaSession, SessionStatus
from app.repositories.agenda_repository import AgendaRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.agenda import AgendaConfigurationUpdate, SessionCreate, SessionUpdate


logger = logging.getLogger(__name__)
SPEAKER_FIELDS = {
    "ponente", "afiliacion", "descripcion_ponente",
    "foto_ponente_url", "es_conferencista_principal",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_session_by_id_or_raise(session_id: uuid.UUID, repo: AgendaRepository) -> AgendaSession:
    session = repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return session


def list_sessions(
    repo: AgendaRepository, day: Optional[str] = None, modality: Optional[str] = None,
    track: Optional[str] = None, event_type: Optional[str] = None,
    salon: Optional[str] = None, venue_id: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
) -> List[AgendaSession]:
    return repo.get_all(
        day=day, modality=modality, track=track, event_type=event_type,
        salon=salon, venue_id=venue_id, search=search,
    )


def _validate_day(day: str, repo: AgendaRepository) -> None:
    config = repo.get_configuration()
    if day not in config.conference_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El día no pertenece al calendario vigente del congreso.",
        )


def _resolve_venue_and_room(
    venue_id: uuid.UUID | None, requested_room: str | None, capacity: int,
    repo: AgendaRepository,
):
    if venue_id is None:
        if not requested_room:
            raise HTTPException(status_code=422, detail="La sesión requiere salón o sede.")
        return None, requested_room

    venue = VenueRepository(repo.db).get(venue_id)
    if not venue or not venue.is_active:
        raise HTTPException(status_code=422, detail="La sede no existe o está inactiva.")
    if capacity > venue.capacity:
        raise HTTPException(
            status_code=422,
            detail=f"Los cupos de la sesión superan la capacidad de la sede ({venue.capacity}).",
        )
    return venue, venue.name


def _validate_overlap(
    venue_id: uuid.UUID | None, day: str, start: str, end: str,
    repo: AgendaRepository, exclude_session_id: uuid.UUID | None = None,
) -> None:
    if venue_id and repo.has_overlap(venue_id, day, start, end, exclude_session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La sede ya tiene una sesión que se cruza con este horario.",
        )


def _publish_legacy_event(routing_key: str, payload: dict, repo: AgendaRepository) -> None:
    """Conserva el contrato actual, ahora con envelope común y rollback explícito."""
    try:
        publish_event(routing_key, payload)
    except Exception as exc:
        logger.error("No se pudo publicar %s: %s", routing_key, exc)
        repo.rollback()
        raise HTTPException(
            status_code=503,
            detail="No fue posible confirmar la operación en el bus de eventos.",
        ) from exc


def create_session(data: SessionCreate, author_id: uuid.UUID, repo: AgendaRepository) -> AgendaSession:
    _validate_day(data.dia, repo)
    venue, room = _resolve_venue_and_room(data.venue_id, data.salon, data.cupos_totales, repo)
    _validate_overlap(data.venue_id, data.dia, data.hora_inicio, data.hora_fin, repo)

    speaker = repo.get_or_create_speaker(
        data.ponente, data.afiliacion, data.descripcion_ponente,
        data.foto_ponente_url, data.es_conferencista_principal,
    )
    session_data = data.model_dump(exclude=SPEAKER_FIELDS | {"salon"})
    session = AgendaSession(
        **session_data, salon=room, speaker_id=speaker.id,
        created_by=author_id, updated_at=_now(),
    )
    repo.add(session)
    event_id = uuid.uuid4()
    _publish_legacy_event("ponencia.creada", {
        "event_id": str(event_id),
        "event": "ponencia.creada",
        "occurred_at": _now().isoformat(),
        "session_id": str(session.id),
        "titulo": session.titulo,
        "ponente": session.ponente,
        "dia": session.dia,
        "hora_inicio": session.hora_inicio,
    }, repo)
    repo.commit()
    return repo.get_by_id(session.id)


def update_session(
    session_id: uuid.UUID, data: SessionUpdate, repo: AgendaRepository,
) -> AgendaSession:
    session = get_session_by_id_or_raise(session_id, repo)
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return session

    resulting_day = update_data.get("dia", session.dia)
    resulting_start = update_data.get("hora_inicio", session.hora_inicio)
    resulting_end = update_data.get("hora_fin", session.hora_fin)
    if resulting_end <= resulting_start:
        raise HTTPException(status_code=422, detail="La hora final debe ser posterior a la inicial.")
    _validate_day(resulting_day, repo)

    resulting_venue_id = update_data.get("venue_id", session.venue_id)
    resulting_capacity = update_data.get("cupos_totales", session.cupos_totales)
    if resulting_capacity < session.inscritos:
        raise HTTPException(status_code=409, detail="Los cupos no pueden quedar por debajo de los inscritos.")
    requested_room = update_data.get("salon", session.salon)
    _, resulting_room = _resolve_venue_and_room(
        resulting_venue_id, requested_room, resulting_capacity, repo,
    )
    _validate_overlap(
        resulting_venue_id, resulting_day, resulting_start, resulting_end,
        repo, exclude_session_id=session.id,
    )

    before = {
        key: getattr(session, key)
        for key in (
            "titulo", "dia", "hora_inicio", "hora_fin", "salon", "venue_id",
            "modalidad", "status_logistico", "cupos_totales", "link_virtual",
        )
    }
    if any(key in update_data for key in SPEAKER_FIELDS):
        speaker = repo.get_or_create_speaker(
            update_data.get("ponente", session.ponente),
            update_data.get("afiliacion", session.afiliacion),
            update_data.get("descripcion_ponente", session.descripcion_ponente),
            update_data.get("foto_ponente_url", session.foto_ponente_url),
            update_data.get("es_conferencista_principal", session.es_conferencista_principal),
        )
        session.speaker_id = speaker.id
        for field in SPEAKER_FIELDS:
            update_data.pop(field, None)

    update_data["salon"] = resulting_room
    update_data["venue_id"] = resulting_venue_id
    if resulting_room != session.salon:
        session.salon_anterior = session.salon
        if "status_logistico" not in update_data:
            session.status_logistico = SessionStatus.CAMBIO_SALON
    for field, value in update_data.items():
        setattr(session, field, value)
    session.updated_at = _now()
    repo.flush()

    changes = {
        key: getattr(session, key)
        for key, old_value in before.items()
        if getattr(session, key) != old_value
    }
    if changes:
        affected = repo.get_registered_user_ids(session.id)
        if affected:
            _publish_legacy_event("agenda.sesion_actualizada", {
                "event_id": str(uuid.uuid4()),
                "event": "agenda.sesion_actualizada",
                "occurred_at": _now().isoformat(),
                "session_id": str(session.id),
                "titulo": session.titulo,
                "cambios": {
                    key: (value.value if hasattr(value, "value") else str(value) if isinstance(value, uuid.UUID) else value)
                    for key, value in changes.items()
                },
                "afectados": affected,
            }, repo)
    repo.commit()
    return repo.get_by_id(session.id)


def delete_session(session_id: uuid.UUID, repo: AgendaRepository) -> None:
    session = get_session_by_id_or_raise(session_id, repo)
    if repo.has_attendance(session_id):
        raise HTTPException(
            status_code=409,
            detail="La sesión tiene evidencia de asistencia y no puede eliminarse.",
        )
    repo.delete(session)
    repo.commit()


def toggle_registration(
    session_id: uuid.UUID, user_id: uuid.UUID, repo: AgendaRepository,
) -> tuple[bool, int]:
    session = repo.get_by_id_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    try:
        if repo.is_user_registered(session.id, user_id):
            repo.remove_registration(session.id, user_id)
            registered = False
        else:
            current_count = repo.count_registrations(session.id)
            if session.cupos_totales > 0 and current_count >= session.cupos_totales:
                raise HTTPException(status_code=409, detail="No hay cupos disponibles.")
            repo.add_registration(session.id, user_id)
            registered = True
        session.inscritos = repo.count_registrations(session.id)
        session.updated_at = _now()
        repo.commit()
        return registered, session.inscritos
    except IntegrityError:
        repo.rollback()
        refreshed = get_session_by_id_or_raise(session_id, repo)
        registered = repo.is_user_registered(session_id, user_id)
        return registered, repo.count_registrations(refreshed.id)


def get_user_registered_sessions(user_id: uuid.UUID, repo: AgendaRepository) -> List[AgendaSession]:
    return repo.get_user_registered_sessions(user_id)


def get_unique_speakers(repo: AgendaRepository, principal_only: bool = False) -> List[dict]:
    speakers = repo.get_all_speakers(principal_only=principal_only)
    result = [{
        "ponente": speaker.nombre,
        "afiliacion": speaker.afiliacion,
        "descripcion_ponente": speaker.descripcion,
        "foto_ponente_url": speaker.foto_url,
        "es_conferencista_principal": speaker.es_principal,
        "sesiones": [{
            "id": str(session.id), "titulo": session.titulo,
            "dia": session.dia, "hora_inicio": session.hora_inicio,
        } for session in speaker.sesiones],
    } for speaker in speakers]
    return sorted(result, key=lambda item: item["ponente"].lower())


def toggle_link_verified(session_id: uuid.UUID, repo: AgendaRepository) -> AgendaSession:
    session = get_session_by_id_or_raise(session_id, repo)
    session.link_verificado = not session.link_verificado
    session.updated_at = _now()
    repo.commit()
    return repo.get_by_id(session.id)


def get_configuration(repo: AgendaRepository):
    config = repo.get_configuration()
    repo.commit()
    repo.refresh(config)
    return config


def configuration_etag(version: int) -> str:
    return f'"agenda-config-v{version}"'


def update_configuration(
    data: AgendaConfigurationUpdate, expected_etag: str | None,
    actor_id: uuid.UUID, repo: AgendaRepository,
):
    if not expected_etag:
        raise HTTPException(status_code=428, detail="Se requiere If-Match para actualizar el calendario.")
    config = repo.get_configuration(for_update=True)
    if expected_etag.strip() not in {configuration_etag(config.version), "*"}:
        raise HTTPException(status_code=412, detail="La configuración cambió; vuelve a cargarla.")

    removed_days = set(config.conference_days) - set(data.conference_days)
    if removed_days:
        used_day = repo.db.query(AgendaSession.id).filter(AgendaSession.dia.in_(removed_days)).first()
        if used_day:
            raise HTTPException(
                status_code=409,
                detail="No se puede retirar un día que ya tiene sesiones; reprográmalas primero.",
            )
    config.edition_label = data.edition_label
    config.conference_days = list(data.conference_days)
    config.timezone = data.timezone
    config.version += 1
    config.updated_by = actor_id
    config.updated_at = _now()
    repo.commit()
    repo.refresh(config)
    return config
