"""App model — represents a registered application module."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel

if TYPE_CHECKING:
    from dhanada.auth.models.user_app import UserApp


class App(BaseModel):
    """A registered application module (e.g. CRM, Accounting, HR)."""

    __tablename__ = "apps"

    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique slug identifier (e.g. 'crm', 'accounting')",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable name (e.g. 'CRM', 'Accounting')",
    )
    schema_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="PostgreSQL schema name for this app's data",
    )

    user_app_links: Mapped[list["UserApp"]] = relationship(
        "UserApp",
        back_populates="app",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<App(id={self.id}, slug={self.slug})>"
