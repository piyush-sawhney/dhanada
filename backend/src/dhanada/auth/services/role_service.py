"""Role-based access control service."""

import uuid
from dataclasses import dataclass
from typing import List

from dhanada.auth.db.repository import RoleRepository, UserRepository
from dhanada.auth.exceptions import (
    PermissionDeniedError,
    UserNotFoundError,
)


@dataclass
class PermissionCheck:
    """Result of a permission check."""

    allowed: bool
    resource: str
    action: str


class RoleService:
    """Role and permission management."""

    def __init__(
        self,
        role_repo: RoleRepository,
        user_repo: UserRepository,
    ) -> None:
        self._role_repo = role_repo
        self._user_repo = user_repo

    async def assign_role(self, user_id: uuid.UUID, role_name: str) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User UUID.
            role_name: Role name (e.g., "admin", "editor").

        Returns:
            True if assignment succeeded.
        """
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        role = await self._role_repo.get_by_name(role_name)
        if role is None:
            return False

        return await self._role_repo.assign_role_to_user(user_id, role.id)

    async def revoke_role(self, user_id: uuid.UUID, role_name: str) -> bool:
        """Revoke a role from a user."""
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        role = await self._role_repo.get_by_name(role_name)
        if role is None:
            return False

        return await self._role_repo.remove_role_from_user(user_id, role.id)

    async def get_user_roles(self, user_id: uuid.UUID) -> List[str]:
        """Get all role names for a user."""
        roles = await self._role_repo.get_user_roles(user_id)
        return [role.name for role in roles]

    async def check_permission(
        self,
        user_id: uuid.UUID,
        resource: str,
        action: str,
    ) -> PermissionCheck:
        """Check if a user has a specific permission.

        Args:
            user_id: User UUID.
            resource: Resource name (e.g., "users", "posts").
            action: Action name (e.g., "read", "write", "delete").

        Returns:
            PermissionCheck result.
        """
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        if user.is_superuser:
            return PermissionCheck(allowed=True, resource=resource, action=action)

        allowed = await self._role_repo.check_permission(user_id, resource, action)
        return PermissionCheck(allowed=allowed, resource=resource, action=action)

    async def assert_permission(
        self,
        user_id: uuid.UUID,
        resource: str,
        action: str,
    ) -> None:
        """Assert that a user has a permission, raising if denied.

        Raises:
            PermissionDeniedError: User lacks the required permission.
        """
        result = await self.check_permission(user_id, resource, action)
        if not result.allowed:
            raise PermissionDeniedError(
                f"Permission denied: {resource}:{action}",
                hint=f"Contact an administrator to request '{resource}:{action}' access",
            )

    async def create_role(
        self, name: str, description: str | None = None
    ) -> bool:
        """Create a new role."""
        existing = await self._role_repo.get_by_name(name)
        if existing is not None:
            return False
        await self._role_repo.create(
            name=name, description=description, is_system=False
        )
        return True

    async def add_permission(
        self, role_name: str, resource: str, action: str
    ) -> bool:
        """Add a permission to a role."""
        role = await self._role_repo.get_by_name(role_name)
        if role is None:
            return False
        await self._role_repo.create(
            role_id=role.id, resource=resource, action=action
        )
        return True

    async def get_user_permissions(self, user_id: uuid.UUID) -> List[str]:
        """Get all permission strings for a user."""
        return await self._role_repo.get_permissions(user_id)