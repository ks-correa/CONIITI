from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Index, String, UniqueConstraint
from app.database import Base
from app.models.roles import UserRole
import uuid

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_document", "document", unique=True),
        Index("ix_users_institutional_code", "institutional_code", unique=True),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, nullable=False)
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    email = Column(String, nullable=False)
    role = Column(
        Enum(UserRole, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.EXTERNAL,
    )
    institution = Column(String, nullable=True)
    career = Column(String(255), nullable=True)
    gender = Column(String(80), nullable=True)
    document = Column(String(100), nullable=True)
    institutional_code = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    profile_completed_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def profile_completed(self) -> bool:
        return self.profile_completed_at is not None
