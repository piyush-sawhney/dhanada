"""Role, UserRole, and RolePermission models."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel

if TYPE_CHECKING:
    from dhanada.auth.models.user import User


class UserRole(BaseModel):
    """Association model between users and roles with audit support."""

    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.roles.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_role_links",
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="user_role_links",
    )

    def __repr__(self) -> str:
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


class Role(BaseModel):
    """Role model for RBAC."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    user_role_links: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    users: AssociationProxy[list["User"]] = association_proxy("user_role_links", "user")

    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"


class RolePermission(BaseModel):
    """Permission model - resource:action pairs bound to roles."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    resource: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )

    __table_args__ = (  # type: ignore[assignment]
        UniqueConstraint("role_id", "resource", "action", name="uq_role_resource_action"),
        {"schema": "auth"},
    )

    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return (
            f"<RolePermission(role_id={self.role_id}, "
            f"resource={self.resource}, action={self.action})>"
        )
