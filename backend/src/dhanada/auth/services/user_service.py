"""User management service."""

import uuid

from dhanada.auth.auth.passwords import PasswordManager
from dhanada.auth.db.repository import UserRepository
from dhanada.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from dhanada.auth.models.user import User


class UserService:
    """User registration, authentication, and profile management."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_manager: PasswordManager,
    ) -> None:
        self._user_repo = user_repo
        self._password_manager = password_manager

    async def register(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
        created_by_id: uuid.UUID | None = None,
    ) -> User:
        """Register a new user."""
        existing_email = await self._user_repo.get_by_email(email)
        if existing_email is not None:
            raise UserAlreadyExistsError(
                f"Email '{email}' is already registered",
                hint="Try logging in instead, or use a different email",
            )

        existing_username = await self._user_repo.get_by_username(username)
        if existing_username is not None:
            raise UserAlreadyExistsError(
                f"Username '{username}' is already taken",
                hint="Choose a different username",
            )

        password_hash = self._password_manager.hash_password(password)
        user = await self._user_repo.create(
            email=email,
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            created_by_id=created_by_id,
        )
        return user

    async def register_superuser(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        """Register the first superuser.

        Same as register() but sets is_superuser=True.
        Caller is responsible for checking that no users exist.
        """
        existing_email = await self._user_repo.get_by_email(email)
        if existing_email is not None:
            raise UserAlreadyExistsError(
                f"Email '{email}' is already registered",
                hint="Use a different email",
            )

        existing_username = await self._user_repo.get_by_username(username)
        if existing_username is not None:
            raise UserAlreadyExistsError(
                f"Username '{username}' is already taken",
                hint="Choose a different username",
            )

        password_hash = self._password_manager.hash_password(password)
        user = await self._user_repo.create(
            email=email,
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            is_superuser=True,
        )
        return user

    async def authenticate(
        self,
        email: str,
        password: str,
    ) -> User:
        """Authenticate a user with email and password."""
        user = await self._user_repo.get_by_email(email)
        if user is None or user.deleted_at is not None:
            raise InvalidCredentialsError(
                "Invalid email or password",
                hint="Check your credentials or register a new account",
            )
        if not self._password_manager.verify_password(password, user.password_hash):
            raise InvalidCredentialsError(
                "Invalid email or password",
                hint="Check your credentials or reset your password",
            )
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        """Get a user by ID.

        Args:
            user_id: User UUID.

        Returns:
            User instance.

        Raises:
            UserNotFoundError: User not found.
        """
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        return await self._user_repo.get_by_email(email)

    async def change_password(
        self,
        user_id: uuid.UUID,
        old_password: str,
        new_password: str,
        updated_by_id: uuid.UUID | None = None,
    ) -> User:
        """Change a user's password."""
        user = await self.get_by_id(user_id)
        if not self._password_manager.verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError(
                "Current password is incorrect",
                hint="Enter your current password correctly",
            )
        new_hash = self._password_manager.hash_password(new_password)
        updated = await self._user_repo.update(
            user_id, password_hash=new_hash, updated_by_id=updated_by_id,
        )
        return updated

    async def update_profile(
        self,
        user_id: uuid.UUID,
        full_name: str | None = None,
        updated_by_id: uuid.UUID | None = None,
    ) -> User:
        """Update user profile information."""
        updates: dict = {}
        if full_name is not None:
            updates["full_name"] = full_name
        updated = await self._user_repo.update(user_id, updated_by_id=updated_by_id, **updates)
        if updated is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return updated

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Update last login timestamp."""
        await self._user_repo.update_last_login(user_id)

    async def activate_user(
        self,
        user_id: uuid.UUID,
        updated_by_id: uuid.UUID | None = None,
    ) -> User:
        """Activate a user account (set is_active=True)."""
        user = await self._user_repo.update(
            user_id, is_active=True, updated_by_id=updated_by_id,
        )
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return user

    async def set_password(
        self,
        user_id: uuid.UUID,
        password: str,
        updated_by_id: uuid.UUID | None = None,
    ) -> User:
        """Set a user's password without verifying the old one.

        Used during first-time setup and admin-forced password reset.
        """
        user = await self.get_by_id(user_id)
        new_hash = self._password_manager.hash_password(password)
        updated = await self._user_repo.update(
            user_id, password_hash=new_hash, updated_by_id=updated_by_id,
        )
        return updated
