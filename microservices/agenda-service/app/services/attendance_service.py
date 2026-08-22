import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError

from app.models.agenda import (
    AttendanceMethod, AttendanceVerificationToken, SessionAttendance,
)
from app.repositories.agenda_repository import AgendaRepository
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import EligibilitySnapshotRequest
from app.services.event_outbox import enqueue_event


ATTENDANCE_KEY = os.getenv("ATTENDANCE_SIGNING_KEY") or os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
ATTENDANCE_ISSUER = "coniiti-agenda-service"
ATTENDANCE_AUDIENCE = "coniiti-attendance"
KEY_VERSION = int(os.getenv("ATTENDANCE_KEY_VERSION", "1"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _jti_hash(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def _session_or_404(session_id: uuid.UUID, repo: AgendaRepository):
    session = repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return session


def _validate_attendance_window(session, repo: AgendaRepository, now: datetime):
    config = repo.get_configuration()
    tz = ZoneInfo(config.timezone)
    start_local = datetime.fromisoformat(f"{session.dia}T{session.hora_inicio}:00").replace(tzinfo=tz)
    end_local = datetime.fromisoformat(f"{session.dia}T{session.hora_fin}:00").replace(tzinfo=tz)
    opens = start_local - timedelta(minutes=int(os.getenv("ATTENDANCE_OPEN_MINUTES_BEFORE", "60")))
    closes = end_local + timedelta(minutes=int(os.getenv("ATTENDANCE_CLOSE_MINUTES_AFTER", "180")))
    current_local = now.astimezone(tz)
    if current_local < opens or current_local > closes:
        raise HTTPException(status_code=409, detail="La ventana de asistencia no está abierta.")


def issue_token(
    session_id: uuid.UUID, issued_by: uuid.UUID, ttl_seconds: int,
    max_uses: int, agenda_repo: AgendaRepository, attendance_repo: AttendanceRepository,
):
    if not ATTENDANCE_KEY:
        raise HTTPException(status_code=503, detail="Firma de asistencia no configurada.")
    _session_or_404(session_id, agenda_repo)
    now = _now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    jti = str(uuid.uuid4())
    token_row = AttendanceVerificationToken(
        session_id=session_id, jti_hash=_jti_hash(jti), issued_by=issued_by,
        issued_at=now, expires_at=expires_at, max_uses=max_uses,
        key_version=KEY_VERSION,
    )
    attendance_repo.add(token_row)
    attendance_repo.commit()
    token = jwt.encode({
        "iss": ATTENDANCE_ISSUER,
        "aud": ATTENDANCE_AUDIENCE,
        "type": "attendance",
        "session_id": str(session_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "kv": KEY_VERSION,
    }, ATTENDANCE_KEY, algorithm="HS256")
    return {"token": token, "session_id": session_id, "expires_at": expires_at, "max_uses": max_uses}


def _decode_token_for_checkin(token: str) -> dict:
    if not ATTENDANCE_KEY:
        raise HTTPException(status_code=503, detail="Firma de asistencia no configurada.")
    try:
        payload = jwt.decode(
            token, ATTENDANCE_KEY, algorithms=["HS256"],
            issuer=ATTENDANCE_ISSUER, audience=ATTENDANCE_AUDIENCE,
            options={"verify_exp": False, "verify_nbf": False},
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token de asistencia inválido.") from exc
    if payload.get("type") != "attendance" or not payload.get("jti") or not payload.get("session_id"):
        raise HTTPException(status_code=401, detail="Token de asistencia incompleto.")
    if int(payload.get("kv", -1)) != KEY_VERSION:
        raise HTTPException(status_code=401, detail="Versión de firma de asistencia no vigente.")
    return payload


def check_in(
    session_id: uuid.UUID, user_id: uuid.UUID, encoded_token: str,
    agenda_repo: AgendaRepository, attendance_repo: AttendanceRepository,
):
    payload = _decode_token_for_checkin(encoded_token)
    try:
        token_session_id = uuid.UUID(str(payload["session_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Token de asistencia inválido.") from exc
    if token_session_id != session_id:
        raise HTTPException(status_code=409, detail="El token pertenece a otra sesión.")

    existing = attendance_repo.get_attendance(session_id, user_id)
    if existing and existing.revoked_at is None:
        return existing
    if existing and existing.revoked_at is not None:
        raise HTTPException(status_code=409, detail="La asistencia fue revocada; requiere revisión de staff.")

    token_row = attendance_repo.get_token_by_hash(_jti_hash(payload["jti"]), for_update=True)
    if not token_row or token_row.session_id != session_id:
        raise HTTPException(status_code=401, detail="Token de asistencia no reconocido.")
    now = _now()
    if now.timestamp() < int(payload.get("nbf", 0)):
        raise HTTPException(status_code=401, detail="Token de asistencia aún no vigente.")
    if token_row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Token de asistencia revocado.")
    if now > _aware(token_row.expires_at) or now.timestamp() > int(payload.get("exp", 0)):
        raise HTTPException(status_code=401, detail="Token de asistencia expirado.")
    if token_row.used_count >= token_row.max_uses:
        raise HTTPException(status_code=409, detail="Token de asistencia ya consumido.")

    session = _session_or_404(session_id, agenda_repo)
    _validate_attendance_window(session, agenda_repo, now)
    require_registration = os.getenv("ATTENDANCE_REQUIRE_REGISTRATION", "true").lower() == "true"
    if require_registration and not attendance_repo.is_registered(session_id, user_id):
        raise HTTPException(status_code=403, detail="La asistencia requiere preinscripción previa.")

    token_row.used_count += 1
    attendance = SessionAttendance(
        session_id=session_id, user_id=user_id, confirmed_at=now,
        confirmed_by=user_id, method=AttendanceMethod.QR.value,
        verification_token_id=token_row.id,
    )
    try:
        attendance_repo.add(attendance)
        event_id = uuid.uuid4()
        enqueue_event(attendance_repo.db, "asistencia.confirmada", {
            "event_id": str(event_id),
            "event": "asistencia.confirmada",
            "occurred_at": now.isoformat(),
            "session_id": str(session_id),
            "user_id": str(user_id),
            "attendance_id": str(attendance.id),
            "confirmed_at": now.isoformat(),
        })
        attendance_repo.commit()
    except IntegrityError:
        attendance_repo.rollback()
        concurrent = attendance_repo.get_attendance(session_id, user_id, include_revoked=False)
        if concurrent:
            return concurrent
        raise
    attendance_repo.refresh(attendance)
    return attendance


def manual_check_in(
    session_id: uuid.UUID, user_id: uuid.UUID, actor_id: uuid.UUID, reason: str,
    agenda_repo: AgendaRepository, attendance_repo: AttendanceRepository,
):
    _session_or_404(session_id, agenda_repo)
    existing = attendance_repo.get_attendance(session_id, user_id)
    now = _now()
    if existing:
        if existing.revoked_at is None:
            return existing
        existing.revoked_at = None
        existing.revocation_reason = None
        existing.confirmed_at = now
        existing.confirmed_by = actor_id
        existing.method = AttendanceMethod.MANUAL.value
        existing.confirmation_note = reason
        attendance = existing
    else:
        attendance = SessionAttendance(
            session_id=session_id, user_id=user_id, confirmed_at=now,
            confirmed_by=actor_id, method=AttendanceMethod.MANUAL.value,
            confirmation_note=reason,
        )
        attendance_repo.add(attendance)
    event_id = uuid.uuid4()
    enqueue_event(attendance_repo.db, "asistencia.confirmada", {
        "event_id": str(event_id), "event": "asistencia.confirmada",
        "occurred_at": now.isoformat(), "session_id": str(session_id),
        "user_id": str(user_id), "attendance_id": str(attendance.id),
        "confirmed_at": now.isoformat(),
    })
    attendance_repo.commit()
    attendance_repo.refresh(attendance)
    return attendance


def revoke_attendance(
    session_id: uuid.UUID, attendance_id: uuid.UUID, reason: str,
    repo: AttendanceRepository,
):
    attendance = repo.get_attendance_by_id(session_id, attendance_id, for_update=True)
    if not attendance:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada.")
    if attendance.revoked_at is None:
        attendance.revoked_at = _now()
        attendance.revocation_reason = reason
        repo.commit()
        repo.refresh(attendance)
    return attendance


def eligibility_snapshot(data: EligibilitySnapshotRequest, repo: AttendanceRepository):
    rows = repo.eligibility_snapshot(
        data.session_ids, data.confirmed_from, data.confirmed_to,
        data.require_registration,
    )
    items = [{
        "user_id": row.user_id,
        "session_id": row.session_id,
        "attendance_id": row.id,
        "confirmed_at": row.confirmed_at,
    } for row in rows]
    return {"items": items, "total": len(items)}
