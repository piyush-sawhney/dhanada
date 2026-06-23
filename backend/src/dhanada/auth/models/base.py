"""Base model with common fields."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship

if TYPE_CHECKING:
    from dhanada.auth.models.user import User


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class AuditMixin:
    """Mixin for created_by and updated_by audit fields."""

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    @declared_attr
    def created_by(cls) -> Mapped[Optional["User"]]:
        return relationship(
            "User",
            foreign_keys=[cls.created_by_id],  # type: ignore[list-item]
            lazy="selectin",
        )

    @declared_attr
    def updated_by(cls) -> Mapped[Optional["User"]]:
        return relationship(
            "User",
            foreign_keys=[cls.updated_by_id],  # type: ignore[list-item]
            lazy="selectin",
        )


class BaseModel(Base, UUIDMixin, TimestampMixin, AuditMixin):
    """Base model with UUID, timestamps, and audit fields."""

    __abstract__ = True
    __table_args__ = {"schema": "auth"}

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
