import uuid
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models.agenda import (
    AgendaConfiguration, AgendaSession, SessionAttendance, Speaker, Venue,
    session_registrations,
)


class AgendaRepository:
    """Acceso transaccional a agenda, configuración y preinscripciones."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, session_id: uuid.UUID) -> Optional[AgendaSession]:
        return (
            self.db.query(AgendaSession)
            .options(
                joinedload(AgendaSession.speaker),
                joinedload(AgendaSession.venue).joinedload(Venue.resources),
            )
            .filter(AgendaSession.id == session_id)
            .first()
        )

    def get_by_id_for_update(self, session_id: uuid.UUID) -> Optional[AgendaSession]:
        return (
            self.db.query(AgendaSession)
            .options(joinedload(AgendaSession.speaker), joinedload(AgendaSession.venue))
            .filter(AgendaSession.id == session_id)
            .with_for_update(of=AgendaSession)
            .first()
        )

    def get_all(
        self, day: str = None, modality: str = None, track: str = None,
        event_type: str = None, salon: str = None, venue_id: uuid.UUID = None,
        search: str = None, principal_only: bool = False,
    ) -> List[AgendaSession]:
        query = (
            self.db.query(AgendaSession)
            .join(AgendaSession.speaker)
            .options(
                contains_eager(AgendaSession.speaker),
                joinedload(AgendaSession.venue).joinedload(Venue.resources),
            )
        )
        if day:
            query = query.filter(AgendaSession.dia == day)
        if modality:
            query = query.filter(AgendaSession.modalidad == modality)
        if track:
            query = query.filter(AgendaSession.track == track)
        if event_type:
            query = query.filter(AgendaSession.event_type == event_type)
        if salon:
            query = query.filter(AgendaSession.salon == salon)
        if venue_id:
            query = query.filter(AgendaSession.venue_id == venue_id)
        if principal_only:
            query = query.filter(Speaker.es_principal.is_(True))
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                AgendaSession.titulo.ilike(term)
                | Speaker.nombre.ilike(term)
                | AgendaSession.descripcion.ilike(term)
            )
        return query.order_by(AgendaSession.dia, AgendaSession.hora_inicio).all()

    def get_all_speakers(self, principal_only: bool = False) -> List[Speaker]:
        query = self.db.query(Speaker).options(joinedload(Speaker.sesiones))
        if principal_only:
            query = query.filter(Speaker.es_principal.is_(True))
        return query.all()

    def get_or_create_speaker(
        self, nombre: str, afiliacion: str | None, descripcion: str | None,
        foto_url: str | None, es_principal: bool,
    ) -> Speaker:
        norm_nombre = nombre.strip()
        norm_afiliacion = (afiliacion or "").strip()
        speaker = self.db.query(Speaker).filter(
            Speaker.nombre == norm_nombre, Speaker.afiliacion == norm_afiliacion,
        ).first()
        if speaker:
            if descripcion is not None:
                speaker.descripcion = descripcion
            if foto_url is not None:
                speaker.foto_url = foto_url
            if es_principal:
                speaker.es_principal = True
        else:
            speaker = Speaker(
                nombre=norm_nombre, afiliacion=norm_afiliacion,
                descripcion=descripcion, foto_url=foto_url,
                es_principal=es_principal,
            )
            self.db.add(speaker)
            try:
                with self.db.begin_nested():
                    self.db.flush()
            except IntegrityError:
                speaker = self.db.query(Speaker).filter(
                    Speaker.nombre == norm_nombre,
                    Speaker.afiliacion == norm_afiliacion,
                ).one()
        return speaker

    def add(self, session: AgendaSession) -> AgendaSession:
        self.db.add(session)
        self.db.flush()
        return session

    def delete(self, session: AgendaSession) -> None:
        self.db.execute(
            delete(session_registrations).where(
                session_registrations.c.session_id == session.id,
            )
        )
        self.db.delete(session)

    def has_attendance(self, session_id: uuid.UUID) -> bool:
        return self.db.query(SessionAttendance.id).filter(
            SessionAttendance.session_id == session_id,
        ).first() is not None

    def has_overlap(
        self, venue_id: uuid.UUID, day: str, starts_at: str, ends_at: str,
        exclude_session_id: uuid.UUID | None = None,
    ) -> bool:
        query = self.db.query(AgendaSession.id).filter(
            AgendaSession.venue_id == venue_id,
            AgendaSession.dia == day,
            AgendaSession.hora_inicio < ends_at,
            AgendaSession.hora_fin > starts_at,
        )
        if exclude_session_id:
            query = query.filter(AgendaSession.id != exclude_session_id)
        return query.first() is not None

    def get_configuration(self, for_update: bool = False) -> AgendaConfiguration:
        query = self.db.query(AgendaConfiguration).filter(AgendaConfiguration.id == "default")
        if for_update:
            query = query.with_for_update()
        config = query.first()
        if config is None:
            config = AgendaConfiguration(id="default")
            self.db.add(config)
            self.db.flush()
        return config

    def get_registered_user_ids(self, session_id: uuid.UUID) -> List[str]:
        users = self.db.execute(
            select(session_registrations.c.user_id).where(
                session_registrations.c.session_id == session_id,
            )
        ).all()
        return [str(row.user_id) for row in users]

    def is_user_registered(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return self.db.execute(
            select(session_registrations.c.user_id).where(
                session_registrations.c.user_id == user_id,
                session_registrations.c.session_id == session_id,
            )
        ).first() is not None

    def add_registration(self, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.db.execute(
            session_registrations.insert().values(user_id=user_id, session_id=session_id),
        )

    def remove_registration(self, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.db.execute(
            delete(session_registrations).where(
                session_registrations.c.user_id == user_id,
                session_registrations.c.session_id == session_id,
            )
        )

    def count_registrations(self, session_id: uuid.UUID) -> int:
        return int(self.db.execute(
            select(func.count()).select_from(session_registrations).where(
                session_registrations.c.session_id == session_id,
            )
        ).scalar_one())

    def get_user_registered_sessions(self, user_id: uuid.UUID) -> List[AgendaSession]:
        return (
            self.db.query(AgendaSession)
            .options(
                joinedload(AgendaSession.speaker),
                joinedload(AgendaSession.venue).joinedload(Venue.resources),
            )
            .join(session_registrations, session_registrations.c.session_id == AgendaSession.id)
            .filter(session_registrations.c.user_id == user_id)
            .order_by(AgendaSession.dia, AgendaSession.hora_inicio)
            .all()
        )

    def commit(self) -> None:
        self.db.commit()

    def flush(self) -> None:
        self.db.flush()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance) -> None:
        self.db.refresh(instance)
