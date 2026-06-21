"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel

if TYPE_CHECKING:
    from dhanada.auth.models.role import Role
    from dhanada.auth.models.refresh_token import RefreshToken
    from dhanada.auth.models.totp import TOTPSecret


class User(BaseModel):
    """User model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="auth.user_roles",
        back_populates="users",
        lazy="selectin",
    )
    totp_secret: Mapped[Optional["TOTPSecret"]] = relationship(
        "TOTPSecret",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"