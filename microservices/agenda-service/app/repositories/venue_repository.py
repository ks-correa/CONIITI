import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.agenda import AgendaSession, AssetReferenceOutbox, ResourceState, Venue, VenueResource


class VenueRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[Venue]:
        query = self.db.query(Venue).options(joinedload(Venue.resources)).filter(Venue.deleted_at.is_(None))
        if not include_inactive:
            query = query.filter(Venue.is_active.is_(True))
        return query.order_by(Venue.name).all()

    def get(self, venue_id: uuid.UUID, include_deleted: bool = False, for_update: bool = False) -> Venue | None:
        query = self.db.query(Venue).options(joinedload(Venue.resources)).filter(Venue.id == venue_id)
        if not include_deleted:
            query = query.filter(Venue.deleted_at.is_(None))
        if for_update:
            query = query.with_for_update(of=Venue)
        return query.first()

    def find_by_name(self, name: str, exclude_id: uuid.UUID | None = None) -> Venue | None:
        query = self.db.query(Venue).filter(func.lower(Venue.name) == name.strip().lower(), Venue.deleted_at.is_(None))
        if exclude_id:
            query = query.filter(Venue.id != exclude_id)
        return query.first()

    def count_sessions(self, venue_id: uuid.UUID) -> int:
        return self.db.query(AgendaSession.id).filter(AgendaSession.venue_id == venue_id).count()

    def max_session_capacity(self, venue_id: uuid.UUID) -> int:
        value = self.db.query(func.max(AgendaSession.cupos_totales)).filter(AgendaSession.venue_id == venue_id).scalar()
        return int(value or 0)

    def get_resource(self, venue_id: uuid.UUID, resource_id: uuid.UUID, for_update: bool = False) -> VenueResource | None:
        query = self.db.query(VenueResource).filter(
            VenueResource.id == resource_id,
            VenueResource.venue_id == venue_id,
            VenueResource.deleted_at.is_(None),
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def queue_asset_operation(
        self, resource_id: uuid.UUID, asset_id: uuid.UUID, operation: str,
        finalize_delete: bool = False, slot: str = "primary",
    ) -> AssetReferenceOutbox:
        row = AssetReferenceOutbox(
            resource_id=resource_id, asset_id=asset_id, operation=operation,
            finalize_delete=finalize_delete, slot=slot,
        )
        self.db.add(row)
        return row

    def tombstone(self, resource: VenueResource) -> None:
        resource.state = ResourceState.TOMBSTONED.value
        resource.is_active = False
        resource.deleted_at = datetime.now(timezone.utc)

    def commit(self):
        self.db.commit()

    def flush(self):
        self.db.flush()

    def refresh(self, instance):
        self.db.refresh(instance)

    def rollback(self):
        self.db.rollback()
