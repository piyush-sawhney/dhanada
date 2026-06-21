"""Base model with common fields."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """Base model with UUID and timestamps."""

    __abstract__ = True
    __table_args__ = {"schema": "auth"}

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}