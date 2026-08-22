import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.venue_repository import VenueRepository
from app.schemas.venue import (
    VenueAdminListResponse, VenueCreate, VenueListResponse, VenueRead, VenueResourceCreate,
    VenueResourceRead, VenueResourceUpdate, VenueUpdate,
)
from app.services import venue_service
from app.utils.security import require_staff_or_superuser


router = APIRouter(prefix="/venues", tags=["Sedes y multimedia"])


def get_repo(db: Session = Depends(get_db)) -> VenueRepository:
    return VenueRepository(db)


@router.get("", response_model=VenueListResponse)
def list_public_venues(repo: VenueRepository = Depends(get_repo)):
    venues = venue_service.list_venues(repo)
    return VenueListResponse(total=len(venues), venues=venues)


@router.get("/manage", response_model=VenueAdminListResponse)
def list_all_venues(
    repo: VenueRepository = Depends(get_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    venues = venue_service.list_venues(repo, include_inactive=True)
    return VenueAdminListResponse(total=len(venues), venues=venues)


@router.post("", response_model=VenueRead, status_code=status.HTTP_201_CREATED)
def create_venue(
    data: VenueCreate,
    repo: VenueRepository = Depends(get_repo),
    actor: str = Depends(require_staff_or_superuser),
):
    return venue_service.create_venue(data, uuid.UUID(actor), repo)


@router.get("/{venue_id}", response_model=VenueRead)
def get_venue(venue_id: uuid.UUID, repo: VenueRepository = Depends(get_repo)):
    return venue_service.get_venue(venue_id, repo)


@router.put("/{venue_id}", response_model=VenueRead)
@router.patch("/{venue_id}", response_model=VenueRead)
def update_venue(
    venue_id: uuid.UUID,
    data: VenueUpdate,
    repo: VenueRepository = Depends(get_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    return venue_service.update_venue(venue_id, data, repo)


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_venue(
    venue_id: uuid.UUID,
    repo: VenueRepository = Depends(get_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    venue_service.delete_venue(venue_id, repo)


@router.get("/{venue_id}/resources", response_model=list[VenueResourceRead])
def list_resources(venue_id: uuid.UUID, repo: VenueRepository = Depends(get_repo)):
    venue = venue_service.get_venue(venue_id, repo)
    return venue.active_resources


@router.post(
    "/{venue_id}/resources",
    response_model=VenueResourceRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_resource(
    venue_id: uuid.UUID,
    data: VenueResourceCreate,
    repo: VenueRepository = Depends(get_repo),
    actor: str = Depends(require_staff_or_superuser),
):
    return venue_service.create_resource(venue_id, data, uuid.UUID(actor), repo)


@router.patch("/{venue_id}/resources/{resource_id}", response_model=VenueResourceRead)
def update_resource(
    venue_id: uuid.UUID,
    resource_id: uuid.UUID,
    data: VenueResourceUpdate,
    repo: VenueRepository = Depends(get_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    return venue_service.update_resource(venue_id, resource_id, data, repo)


@router.delete("/{venue_id}/resources/{resource_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_resource(
    venue_id: uuid.UUID,
    resource_id: uuid.UUID,
    repo: VenueRepository = Depends(get_repo),
    _actor: str = Depends(require_staff_or_superuser),
):
    venue_service.delete_resource(venue_id, resource_id, repo)
    return {"status": "pending_or_deleted"}
