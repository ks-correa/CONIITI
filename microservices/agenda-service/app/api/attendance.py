import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.agenda_repository import AgendaRepository
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import (
    AttendanceCheckIn, AttendanceListResponse, AttendanceRead,
    AttendanceRevoke, AttendanceTokenCreate, AttendanceTokenRead,
    EligibilitySnapshotRequest, EligibilitySnapshotResponse, ManualAttendanceCreate,
)
from app.services import attendance_service
from app.utils.security import (
    get_current_user_id, require_internal_service, require_staff_or_superuser,
)


router = APIRouter(tags=["Asistencia"])


def agenda_repo(db: Session = Depends(get_db)):
    return AgendaRepository(db)


def attendance_repo(db: Session = Depends(get_db)):
    return AttendanceRepository(db)


@router.get("/me/attendance", response_model=AttendanceListResponse)
def my_attendance(
    repo: AttendanceRepository = Depends(attendance_repo),
    user_id: str = Depends(get_current_user_id),
):
    items = repo.list_for_user(uuid.UUID(user_id))
    return AttendanceListResponse(total=len(items), items=items)


@router.post(
    "/internal/attendance/eligibility-snapshot",
    response_model=EligibilitySnapshotResponse,
)
def eligibility_snapshot(
    data: EligibilitySnapshotRequest,
    repo: AttendanceRepository = Depends(attendance_repo),
    _service: str = Depends(require_internal_service),
):
    return attendance_service.eligibility_snapshot(data, repo)


@router.post("/{session_id}/attendance-token", response_model=AttendanceTokenRead)
def create_attendance_token(
    session_id: uuid.UUID,
    data: AttendanceTokenCreate,
    agenda: AgendaRepository = Depends(agenda_repo),
    attendance: AttendanceRepository = Depends(attendance_repo),
    actor: str = Depends(require_staff_or_superuser),
):
    return attendance_service.issue_token(
        session_id, uuid.UUID(actor), data.ttl_seconds, data.max_uses,
        agenda, attendance,
    )


@router.post("/{session_id}/attendance/check-in", response_model=AttendanceRead)
def check_in(
    session_id: uuid.UUID,
    data: AttendanceCheckIn,
    agenda: AgendaRepository = Depends(agenda_repo),
    attendance: AttendanceRepository = Depends(attendance_repo),
    user_id: str = Depends(get_current_user_id),
):
    return attendance_service.check_in(
        session_id, uuid.UUID(user_id), data.token, agenda, attendance,
    )


@router.post("/{session_id}/attendance/manual", response_model=AttendanceRead)
def manual_check_in(
    session_id: uuid.UUID,
    data: ManualAttendanceCreate,
    agenda: AgendaRepository = Depends(agenda_repo),
    attendance: AttendanceRepository = Depends(attendance_repo),
    actor: str = Depends(require_staff_or_superuser),
):
    return attendance_service.manual_check_in(
        session_id, data.user_id, uuid.UUID(actor), data.reason,
        agenda, attendance,
    )


@router.get("/{session_id}/attendance", response_model=AttendanceListResponse)
def list_attendance(
    session_id: uuid.UUID,
    include_revoked: bool = False,
    repo: AttendanceRepository = Depends(attendance_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    items = repo.list_for_session(session_id, include_revoked=include_revoked)
    return AttendanceListResponse(total=len(items), items=items)


@router.patch("/{session_id}/attendance/{attendance_id}/revoke", response_model=AttendanceRead)
def revoke_attendance(
    session_id: uuid.UUID,
    attendance_id: uuid.UUID,
    data: AttendanceRevoke,
    repo: AttendanceRepository = Depends(attendance_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    return attendance_service.revoke_attendance(session_id, attendance_id, data.reason, repo)
