from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from . import clients, service
from .database import get_db
from .models import Raffle, RaffleEligibility, RaffleWinner
from .schemas import (
    EligibilityItem,
    EligibilityPage,
    PublicWinner,
    PublishRead,
    RaffleCreate,
    RaffleRead,
    RaffleResult,
    SnapshotRead,
    WinnerRead,
)
from .security import AuthenticatedUser, optional_current_user, require_superuser


router = APIRouter()


def _raffle_read(db: Session, raffle: Raffle) -> RaffleRead:
    return RaffleRead(
        id=raffle.id,
        name=raffle.name,
        description=raffle.description,
        status=raffle.status,
        eligibility_rule=raffle.eligibility_rule,
        winner_count=raffle.winner_count,
        closes_at=raffle.closes_at,
        snapshot_at=raffle.snapshot_at,
        snapshot_hash=raffle.snapshot_hash,
        created_at=raffle.created_at,
        updated_at=raffle.updated_at,
        published_at=raffle.published_at,
        eligible_count=db.query(RaffleEligibility).filter(RaffleEligibility.raffle_id == raffle.id).count(),
        drawn_count=db.query(RaffleWinner).filter(RaffleWinner.raffle_id == raffle.id).count(),
    )


def _profile_names(user_ids: list[str], *, required: bool = True) -> dict[str, str]:
    try:
        return clients.fetch_profile_summaries(user_ids)
    except clients.UpstreamServiceError as exc:
        if required:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {}


@router.get("/", response_model=list[RaffleRead])
def list_all(
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_superuser),
):
    return [_raffle_read(db, raffle) for raffle in service.list_raffles(db)]


@router.post("/", response_model=RaffleRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: RaffleCreate,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_superuser),
):
    return _raffle_read(db, service.create_raffle(db, payload, actor.id))


@router.get("/{raffle_id}", response_model=RaffleRead)
def get_one(
    raffle_id: str,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_superuser),
):
    return _raffle_read(db, service.get_raffle(db, raffle_id))


@router.post("/{raffle_id}/snapshot", response_model=SnapshotRead)
def snapshot(
    raffle_id: str,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_superuser),
):
    raffle = service.lock_snapshot(db, raffle_id)
    eligible_count = db.query(RaffleEligibility).filter(RaffleEligibility.raffle_id == raffle.id).count()
    return SnapshotRead(
        raffle_id=raffle.id,
        status=raffle.status,
        eligible_count=eligible_count,
        snapshot_at=raffle.snapshot_at,
        snapshot_hash=raffle.snapshot_hash,
    )


@router.get("/{raffle_id}/eligibility", response_model=EligibilityPage)
def eligibility(
    raffle_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_superuser),
):
    raffle = service.get_raffle(db, raffle_id)
    if raffle.status == "draft":
        raise HTTPException(status_code=409, detail="El snapshot de elegibilidad aun no existe.")
    query = db.query(RaffleEligibility).filter(RaffleEligibility.raffle_id == raffle.id)
    total = query.count()
    rows = query.order_by(RaffleEligibility.ordinal.asc()).offset((page - 1) * page_size).limit(page_size).all()
    names = _profile_names([row.user_id for row in rows])
    return EligibilityPage(
        items=[
            EligibilityItem(
                user_id=row.user_id,
                ordinal=row.ordinal,
                attendance_evidence=row.attendance_evidence,
                full_name=names.get(row.user_id),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{raffle_id}/draw", response_model=WinnerRead)
def draw(
    raffle_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_superuser),
):
    winner = service.draw_winner(db, raffle_id, actor.id, idempotency_key or "")
    names = _profile_names([winner.user_id], required=False)
    return WinnerRead(
        user_id=winner.user_id,
        full_name=names.get(winner.user_id),
        draw_number=winner.draw_number,
        drawn_at=winner.drawn_at,
        algorithm_version=winner.algorithm_version,
        snapshot_hash=winner.snapshot_hash,
        random_evidence=winner.random_evidence,
        audit_hash=winner.audit_hash,
    )


@router.post("/{raffle_id}/publish", response_model=PublishRead)
def publish(
    raffle_id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_superuser),
):
    raffle = service.publish_raffle(db, raffle_id, actor.id)
    return PublishRead(raffle_id=raffle.id, status=raffle.status, published_at=raffle.published_at)


@router.post("/{raffle_id}/cancel", response_model=RaffleRead)
def cancel(
    raffle_id: str,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_superuser),
):
    return _raffle_read(db, service.cancel_raffle(db, raffle_id))


@router.get("/{raffle_id}/result", response_model=RaffleResult)
def result(
    raffle_id: str,
    db: Session = Depends(get_db),
    current: AuthenticatedUser | None = Depends(optional_current_user),
):
    raffle = service.get_raffle(db, raffle_id)
    privileged = current is not None and current.role == "superuser"
    if raffle.status != "published" and not privileged:
        raise HTTPException(status_code=404, detail="Resultado no publicado.")
    winners = (
        db.query(RaffleWinner)
        .filter(RaffleWinner.raffle_id == raffle.id)
        .order_by(RaffleWinner.draw_number.asc())
        .all()
    )
    if privileged:
        names = _profile_names([winner.user_id for winner in winners], required=False)
        response_winners = [
            WinnerRead(
                user_id=winner.user_id,
                full_name=names.get(winner.user_id),
                draw_number=winner.draw_number,
                drawn_at=winner.drawn_at,
                algorithm_version=winner.algorithm_version,
                snapshot_hash=winner.snapshot_hash,
                random_evidence=winner.random_evidence,
                audit_hash=winner.audit_hash,
            )
            for winner in winners
        ]
    else:
        response_winners = [
            PublicWinner(
                draw_number=winner.draw_number,
                drawn_at=winner.drawn_at,
                winner_reference=winner.audit_hash[:12],
            )
            for winner in winners
        ]
    return RaffleResult(
        raffle_id=raffle.id,
        name=raffle.name,
        status=raffle.status,
        published_at=raffle.published_at,
        winners=response_winners,
    )
