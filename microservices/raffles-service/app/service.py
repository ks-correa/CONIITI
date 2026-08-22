import base64
import hashlib
import json
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import clients
from .models import OutboxEvent, Raffle, RaffleEligibility, RaffleWinner
from .schemas import RaffleCreate


ALGORITHM_VERSION = "coniiti-sha256-rejection-v1"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def get_raffle(db: Session, raffle_id: str, *, lock: bool = False) -> Raffle:
    try:
        parsed = str(uuid.UUID(raffle_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Sorteo no encontrado.") from exc
    statement = select(Raffle).where(Raffle.id == parsed)
    if lock:
        statement = statement.with_for_update()
    raffle = db.execute(statement).scalar_one_or_none()
    if raffle is None:
        raise HTTPException(status_code=404, detail="Sorteo no encontrado.")
    return raffle


def create_raffle(db: Session, payload: RaffleCreate, actor_id: str) -> Raffle:
    raffle = Raffle(
        name=payload.name,
        description=payload.description,
        eligibility_rule=payload.eligibility_rule,
        winner_count=payload.winner_count,
        closes_at=payload.closes_at,
        created_by=actor_id,
    )
    db.add(raffle)
    db.commit()
    db.refresh(raffle)
    return raffle


def list_raffles(db: Session) -> list[Raffle]:
    return db.query(Raffle).order_by(Raffle.created_at.desc()).all()


def _normalize_evidence(items: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    by_user: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen_attendances: dict[str, tuple[str, str, str]] = {}
    for item in items:
        try:
            user_id = str(uuid.UUID(str(item["user_id"])))
            session_id = str(uuid.UUID(str(item["session_id"])))
            attendance_id = str(uuid.UUID(str(item["attendance_id"])))
            raw_confirmed_at = item["confirmed_at"]
            if not isinstance(raw_confirmed_at, str):
                raise ValueError("confirmed_at no es string")
            confirmed_at_value = datetime.fromisoformat(raw_confirmed_at.replace("Z", "+00:00"))
            if confirmed_at_value.tzinfo is None:
                raise ValueError("confirmed_at no incluye zona horaria")
            confirmed_at = confirmed_at_value.astimezone(timezone.utc).isoformat()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Agenda devolvio evidencia de asistencia invalida.") from exc

        signature = (user_id, session_id, confirmed_at)
        previous = seen_attendances.get(attendance_id)
        if previous is not None:
            if previous != signature:
                raise ValueError("Agenda devolvio un attendance_id contradictorio.")
            continue
        seen_attendances[attendance_id] = signature
        by_user[user_id].append(
            {
                "attendance_id": attendance_id,
                "confirmed_at": confirmed_at,
                "session_id": session_id,
            }
        )

    normalized: list[tuple[str, dict[str, Any]]] = []
    for user_id in sorted(by_user):
        evidence = {"attendances": sorted(by_user[user_id], key=lambda value: _canonical(value))}
        normalized.append((user_id, evidence))
    return normalized


def lock_snapshot(db: Session, raffle_id: str) -> Raffle:
    current = get_raffle(db, raffle_id)
    if current.status in {"eligibility_locked", "drawn", "published"}:
        return current
    if current.status != "draft":
        raise HTTPException(status_code=409, detail="El sorteo no admite un nuevo snapshot.")
    closes_at = _aware(current.closes_at)
    if closes_at and now_utc() < closes_at:
        raise HTTPException(status_code=409, detail="La ventana de elegibilidad aun no ha cerrado.")

    try:
        upstream_items = clients.fetch_attendance_snapshot(current.eligibility_rule)
    except clients.UpstreamServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        normalized = _normalize_evidence(upstream_items)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not normalized:
        raise HTTPException(status_code=409, detail="No hay asistentes elegibles para este sorteo.")
    if len(normalized) < current.winner_count:
        raise HTTPException(
            status_code=409,
            detail="La cantidad de ganadores supera el numero de asistentes elegibles.",
        )

    raffle = get_raffle(db, raffle_id, lock=True)
    if raffle.status in {"eligibility_locked", "drawn", "published"}:
        return raffle
    if raffle.status != "draft":
        raise HTTPException(status_code=409, detail="El sorteo no admite un nuevo snapshot.")

    snapshot_at = now_utc()
    canonical_snapshot = [
        {"attendance_evidence": evidence, "ordinal": ordinal, "user_id": user_id}
        for ordinal, (user_id, evidence) in enumerate(normalized, start=1)
    ]
    snapshot_hash = hashlib.sha256(_canonical(canonical_snapshot).encode("utf-8")).hexdigest()
    for ordinal, (user_id, evidence) in enumerate(normalized, start=1):
        db.add(
            RaffleEligibility(
                raffle_id=raffle.id,
                user_id=user_id,
                attendance_evidence=evidence,
                snapshot_at=snapshot_at,
                ordinal=ordinal,
            )
        )
    raffle.status = "eligibility_locked"
    raffle.snapshot_at = snapshot_at
    raffle.snapshot_hash = snapshot_hash
    raffle.updated_at = snapshot_at
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        concurrent = get_raffle(db, raffle_id)
        if concurrent.status in {"eligibility_locked", "drawn", "published"}:
            return concurrent
        raise HTTPException(status_code=409, detail="No se pudo fijar un snapshot unico.") from exc
    db.refresh(raffle)
    return raffle


def _select_index(entropy: bytes, snapshot_hash: str, draw_number: int, candidate_count: int) -> int:
    limit = (1 << 256) - ((1 << 256) % candidate_count)
    counter = 0
    while True:
        digest = hashlib.sha256(
            entropy + bytes.fromhex(snapshot_hash) + draw_number.to_bytes(8, "big") + counter.to_bytes(8, "big")
        ).digest()
        candidate = int.from_bytes(digest, "big")
        if candidate < limit:
            return candidate % candidate_count
        counter += 1


def draw_winner(db: Session, raffle_id: str, actor_id: str, idempotency_key: str) -> RaffleWinner:
    key = idempotency_key.strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key es obligatorio y admite hasta 128 caracteres.")

    try:
        normalized_raffle_id = str(uuid.UUID(raffle_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Sorteo no encontrado.") from exc

    existing = db.query(RaffleWinner).filter(RaffleWinner.idempotency_key == key).first()
    if existing:
        if existing.raffle_id != normalized_raffle_id:
            raise HTTPException(status_code=409, detail="La clave de idempotencia pertenece a otro sorteo.")
        return existing

    raffle = get_raffle(db, normalized_raffle_id, lock=True)
    # A concurrent request may have committed while this transaction waited
    # for the raffle row lock. Re-read the operation key inside the lock.
    existing = db.query(RaffleWinner).filter(RaffleWinner.idempotency_key == key).first()
    if existing:
        if existing.raffle_id != raffle.id:
            raise HTTPException(status_code=409, detail="La clave de idempotencia pertenece a otro sorteo.")
        return existing
    if raffle.status not in {"eligibility_locked", "drawn"}:
        raise HTTPException(status_code=409, detail="Primero fija la elegibilidad; un sorteo publicado no cambia.")
    if not raffle.snapshot_hash or len(raffle.snapshot_hash) != 64:
        raise HTTPException(status_code=409, detail="El snapshot del sorteo no tiene un hash valido.")

    winners = (
        db.query(RaffleWinner)
        .filter(RaffleWinner.raffle_id == raffle.id)
        .order_by(RaffleWinner.draw_number.asc())
        .all()
    )
    if len(winners) >= raffle.winner_count:
        raise HTTPException(status_code=409, detail="Ya se sortearon todos los ganadores configurados.")
    winner_ids = {winner.user_id for winner in winners}
    candidates = (
        db.query(RaffleEligibility)
        .filter(RaffleEligibility.raffle_id == raffle.id)
        .order_by(RaffleEligibility.ordinal.asc())
        .all()
    )
    remaining = [candidate for candidate in candidates if candidate.user_id not in winner_ids]
    if not remaining:
        raise HTTPException(status_code=409, detail="No quedan candidatos sin premio.")

    draw_number = len(winners) + 1
    entropy = secrets.token_bytes(32)
    index = _select_index(entropy, raffle.snapshot_hash or "", draw_number, len(remaining))
    selected = remaining[index]
    drawn_at = now_utc()
    evidence = base64.urlsafe_b64encode(entropy).decode("ascii").rstrip("=")
    audit_payload = {
        "algorithm_version": ALGORITHM_VERSION,
        "draw_number": draw_number,
        "drawn_at": drawn_at.isoformat(),
        "drawn_by": actor_id,
        "idempotency_key": key,
        "raffle_id": raffle.id,
        "random_evidence": evidence,
        "snapshot_hash": raffle.snapshot_hash,
        "winner_user_id": selected.user_id,
    }
    audit_hash = hashlib.sha256(_canonical(audit_payload).encode("utf-8")).hexdigest()
    winner = RaffleWinner(
        raffle_id=raffle.id,
        user_id=selected.user_id,
        drawn_at=drawn_at,
        drawn_by=actor_id,
        draw_number=draw_number,
        idempotency_key=key,
        algorithm_version=ALGORITHM_VERSION,
        snapshot_hash=raffle.snapshot_hash or "",
        random_evidence=evidence,
        audit_hash=audit_hash,
    )
    event_id = str(uuid.uuid4())
    event_payload = {
        "event_id": event_id,
        "event": "premio.adjudicado",
        "raffle_id": raffle.id,
        "winner_user_id": selected.user_id,
        "draw_number": draw_number,
        "drawn_at": drawn_at.isoformat(),
        "audit_hash": audit_hash,
    }
    db.add(winner)
    db.add(OutboxEvent(id=event_id, routing_key="premio.adjudicado", payload=event_payload))
    raffle.status = "drawn"
    raffle.updated_at = drawn_at
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = db.query(RaffleWinner).filter(RaffleWinner.idempotency_key == key).first()
        if replay and replay.raffle_id == raffle.id:
            return replay
        raise HTTPException(status_code=409, detail="El sorteo recibio una operacion concurrente; reintenta.") from exc
    db.refresh(winner)
    return winner


def publish_raffle(db: Session, raffle_id: str, actor_id: str) -> Raffle:
    raffle = get_raffle(db, raffle_id, lock=True)
    if raffle.status == "published":
        return raffle
    if raffle.status != "drawn":
        raise HTTPException(status_code=409, detail="Solo un sorteo realizado se puede publicar.")
    drawn_count = db.query(RaffleWinner).filter(RaffleWinner.raffle_id == raffle.id).count()
    if drawn_count < raffle.winner_count:
        raise HTTPException(
            status_code=409,
            detail=f"Faltan {raffle.winner_count - drawn_count} ganador(es) antes de publicar.",
        )
    raffle.status = "published"
    raffle.published_at = now_utc()
    raffle.published_by = actor_id
    raffle.updated_at = raffle.published_at
    db.commit()
    db.refresh(raffle)
    return raffle


def cancel_raffle(db: Session, raffle_id: str) -> Raffle:
    raffle = get_raffle(db, raffle_id, lock=True)
    if raffle.status == "published":
        raise HTTPException(status_code=409, detail="Un resultado publicado no se puede cancelar.")
    if raffle.status != "cancelled":
        raffle.status = "cancelled"
        raffle.updated_at = now_utc()
        db.commit()
        db.refresh(raffle)
    return raffle
