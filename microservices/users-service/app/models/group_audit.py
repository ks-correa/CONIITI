import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from app.database import Base


class GroupAuditLog(Base):
    __tablename__ = "group_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36), nullable=False, index=True)
    action = Column(String(80), nullable=False)
    subject_user_id = Column(String(36), nullable=True)
    details = Column("metadata", JSON, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
