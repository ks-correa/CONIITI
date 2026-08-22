import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.agenda import (
    AttendanceVerificationToken, SessionAttendance, session_registrations,
)


class AttendanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_token_by_hash(self, jti_hash: str, for_update: bool = False):
        query = self.db.query(AttendanceVerificationToken).filter(
            AttendanceVerificationToken.jti_hash == jti_hash,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_attendance(self, session_id: uuid.UUID, user_id: uuid.UUID, include_revoked: bool = True):
        query = self.db.query(SessionAttendance).filter(
            SessionAttendance.session_id == session_id,
            SessionAttendance.user_id == user_id,
        )
        if not include_revoked:
            query = query.filter(SessionAttendance.revoked_at.is_(None))
        return query.first()

    def get_attendance_by_id(self, session_id: uuid.UUID, attendance_id: uuid.UUID, for_update: bool = False):
        query = self.db.query(SessionAttendance).filter(
            SessionAttendance.session_id == session_id,
            SessionAttendance.id == attendance_id,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def list_for_session(self, session_id: uuid.UUID, include_revoked: bool = False):
        query = self.db.query(SessionAttendance).filter(SessionAttendance.session_id == session_id)
        if not include_revoked:
            query = query.filter(SessionAttendance.revoked_at.is_(None))
        return query.order_by(SessionAttendance.confirmed_at).all()

    def list_for_user(self, user_id: uuid.UUID):
        return self.db.query(SessionAttendance).filter(
            SessionAttendance.user_id == user_id,
            SessionAttendance.revoked_at.is_(None),
        ).order_by(SessionAttendance.confirmed_at).all()

    def is_registered(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return self.db.execute(select(session_registrations.c.user_id).where(
            session_registrations.c.session_id == session_id,
            session_registrations.c.user_id == user_id,
        )).first() is not None

    def eligibility_snapshot(
        self, session_ids: list[uuid.UUID] | None, confirmed_from: datetime | None,
        confirmed_to: datetime | None, require_registration: bool,
    ) -> list[SessionAttendance]:
        query = self.db.query(SessionAttendance).filter(SessionAttendance.revoked_at.is_(None))
        if session_ids:
            query = query.filter(SessionAttendance.session_id.in_(session_ids))
        if confirmed_from:
            query = query.filter(SessionAttendance.confirmed_at >= confirmed_from)
        if confirmed_to:
            query = query.filter(SessionAttendance.confirmed_at <= confirmed_to)
        if require_registration:
            query = query.join(
                session_registrations,
                and_(
                    session_registrations.c.session_id == SessionAttendance.session_id,
                    session_registrations.c.user_id == SessionAttendance.user_id,
                ),
            )
        return query.order_by(SessionAttendance.confirmed_at, SessionAttendance.id).all()

    def add(self, instance):
        self.db.add(instance)
        self.db.flush()
        return instance

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def refresh(self, instance):
        self.db.refresh(instance)
