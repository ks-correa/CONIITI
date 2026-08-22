import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.repositories.agenda_repository import AgendaRepository
from app.schemas.agenda import (
    AgendaConfigurationAdmin, AgendaConfigurationPublic, AgendaConfigurationUpdate,
    SessionCreate, SessionListResponse, SessionRead, SessionRegistrationResponse,
    SessionUpdate,
)
from app.services import agenda_service
from app.utils.security import get_current_user_id, require_staff_or_superuser, require_superuser


router = APIRouter(tags=["Agenda del Congreso"])


def get_agenda_repo(db: DBSession = Depends(get_db)) -> AgendaRepository:
    return AgendaRepository(db)


# Las rutas estáticas se declaran antes de /{session_id} intencionalmente.
@router.get("/config", response_model=AgendaConfigurationPublic)
def get_configuration(response: Response, repo: AgendaRepository = Depends(get_agenda_repo)):
    config = agenda_service.get_configuration(repo)
    response.headers["ETag"] = agenda_service.configuration_etag(config.version)
    response.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
    return config


@router.put("/config", response_model=AgendaConfigurationAdmin)
def update_configuration(
    data: AgendaConfigurationUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    repo: AgendaRepository = Depends(get_agenda_repo),
    user_id: str = Depends(require_superuser),
):
    config = agenda_service.update_configuration(data, if_match, uuid.UUID(user_id), repo)
    response.headers["ETag"] = agenda_service.configuration_etag(config.version)
    return config


@router.get("/speakers", summary="Listar ponentes únicos")
def list_speakers(
    principal_only: bool = Query(False),
    repo: AgendaRepository = Depends(get_agenda_repo),
):
    return agenda_service.get_unique_speakers(repo, principal_only=principal_only)


@router.get("/me/registered", response_model=List[SessionRead])
def get_my_registered_sessions(
    repo: AgendaRepository = Depends(get_agenda_repo),
    user_id: str = Depends(get_current_user_id),
):
    return agenda_service.get_user_registered_sessions(uuid.UUID(user_id), repo)


@router.get("/", response_model=SessionListResponse)
def list_sessions(
    day: Optional[str] = Query(None),
    modality: Optional[str] = Query(None),
    track: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    salon: Optional[str] = Query(None),
    venue_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    repo: AgendaRepository = Depends(get_agenda_repo),
):
    sessions = agenda_service.list_sessions(
        repo, day=day, modality=modality, track=track,
        event_type=event_type, salon=salon, venue_id=venue_id, search=search,
    )
    return SessionListResponse(total=len(sessions), sessions=sessions)


@router.post("/", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    data: SessionCreate,
    repo: AgendaRepository = Depends(get_agenda_repo),
    user_id: str = Depends(require_staff_or_superuser),
):
    return agenda_service.create_session(data, uuid.UUID(user_id), repo)


@router.get("/{session_id}", response_model=SessionRead)
def get_session(session_id: uuid.UUID, repo: AgendaRepository = Depends(get_agenda_repo)):
    return agenda_service.get_session_by_id_or_raise(session_id, repo)


@router.put("/{session_id}", response_model=SessionRead)
def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    repo: AgendaRepository = Depends(get_agenda_repo),
    _user_id: str = Depends(require_staff_or_superuser),
):
    return agenda_service.update_session(session_id, data, repo)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    repo: AgendaRepository = Depends(get_agenda_repo),
    _user_id: str = Depends(require_staff_or_superuser),
):
    agenda_service.delete_session(session_id, repo)


@router.post("/{session_id}/register", response_model=SessionRegistrationResponse)
def toggle_registration(
    session_id: uuid.UUID,
    repo: AgendaRepository = Depends(get_agenda_repo),
    user_id: str = Depends(get_current_user_id),
):
    registered, inscritos = agenda_service.toggle_registration(session_id, uuid.UUID(user_id), repo)
    return SessionRegistrationResponse(
        registered=registered, session_id=session_id, inscritos=inscritos,
    )


@router.patch("/{session_id}/verify-link", response_model=SessionRead)
def toggle_link_verified(
    session_id: uuid.UUID,
    repo: AgendaRepository = Depends(get_agenda_repo),
    _user_id: str = Depends(require_staff_or_superuser),
):
    return agenda_service.toggle_link_verified(session_id, repo)
