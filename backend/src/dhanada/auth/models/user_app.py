"""UserApp model — maps users to registered apps."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel

if TYPE_CHECKING:
    from dhanada.auth.models.app import App
    from dhanada.auth.models.user import User


class UserApp(BaseModel):
    """Maps a user to an app they are registered to use."""

    __tablename__ = "user_apps"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_app_links",
    )
    app: Mapped["App"] = relationship(
        "App",
        back_populates="user_app_links",
    )
    assigned_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_by_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<UserApp(user_id={self.user_id}, app_id={self.app_id})>"
