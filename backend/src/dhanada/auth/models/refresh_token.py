"""RefreshToken model for token rotation tracking."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel

if TYPE_CHECKING:
    from dhanada.auth.models.user import User


class RefreshToken(BaseModel):
    """Tracks refresh tokens for rotation and revocation.

    The actual JWT refresh token is not stored — only a hash.
    This enables detection of token reuse (rotation) and
    revocation without exposing valid tokens.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
        comment="SHA-256 hash of the refresh token",
    )
    family_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        index=True,
        nullable=False,
        comment="Token family for rotation chain tracking",
    )
    parent_token_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Hash of the previous token in the rotation chain",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this token was rotated to a new one",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens",
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_replaced(self) -> bool:
        return self.replaced_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, family_id={self.family_id})>"
