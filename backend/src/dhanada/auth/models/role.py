"""Role and RolePermission models."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel, Base

if TYPE_CHECKING:
    from dhanada.auth.models.user import User


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", PG_UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PG_UUID(as_uuid=True), ForeignKey("auth.roles.id", ondelete="CASCADE"), primary_key=True),
    schema="auth",
)


class Role(BaseModel):
    """Role model for RBAC."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="auth.user_roles",
        back_populates="roles",
        lazy="selectin",
    )
    permissions: Mapped[List["RolePermission"]] = relationship(
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

    __table_args__ = (
        UniqueConstraint("role_id", "resource", "action", name="uq_role_resource_action"),
        {"schema": "auth"},
    )

    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, resource={self.resource}, action={self.action})>"