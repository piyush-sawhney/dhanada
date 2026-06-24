"""User management service."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from dhanada.auth.auth.passwords import PasswordManager
from dhanada.auth.db.repository import UserRepository
from dhanada.auth.exceptions import (
    AccountLockedError,
    CannotDeleteSelfError,
    CannotModifySuperuserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
)
from dhanada.auth.models.user import User


class UserService:
    """User registration, authentication, and profile management."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_manager: PasswordManager,
        lockout_threshold: int = 5,
        lockout_minutes: int = 15,
    ) -> None:
        self._user_repo = user_repo
        self._password_manager = password_manager
        self._lockout_threshold = lockout_threshold
        self._lockout_minutes = lockout_minutes

    async def _generate_unique_username(self, email: str) -> str:
        """Generate a unique username from the email local part."""
        base = email.split("@")[0]
        username = base
        counter = 1
        while await self._user_repo.get_by_username(username):
            username = f"{base}{counter}"
            counter += 1
        return username

    async def register(
        self,
        email: str,
        username: str | None = None,
        password: str = "",
        full_name: str | None = None,
        created_by_id: uuid.UUID | None = None,
    ) -> User:
        """Register a new user."""
        if not password:
            raise ValidationError(
                "Password is required",
                hint="Provide a non-empty password",
            )

        existing_email = await self._user_repo.get_by_email(email)
        if existing_email is not None:
            raise UserAlreadyExistsError(
                f"Email '{email}' is already registered",
                hint="Try logging in instead, or use a different email",
            )

        if username is None:
            username = await self._generate_unique_username(email)
        else:
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
        username: str | None = None,
        password: str = "",
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

        if username is None:
            username = await self._generate_unique_username(email)
        else:
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

        # Check account lockout
        if user.locked_until is not None and user.locked_until > datetime.now(UTC):
            raise AccountLockedError(
                "Account locked.",
                locked_until=user.locked_until.isoformat(),
            )

        if not self._password_manager.verify_password(password, user.password_hash):
            await self._user_repo.increment_failed_attempts(user.id)
            user = await self._user_repo.get(user.id)
            if user is None:
                raise RuntimeError("Failed to retrieve user after incrementing failed attempts")
            if user.failed_login_attempts >= self._lockout_threshold:
                await self._user_repo.lock_account(user.id, self._lockout_minutes)
                now = datetime.now(UTC)
                locked_until = now + timedelta(minutes=self._lockout_minutes)
                raise AccountLockedError(
                    "Account locked.",
                    locked_until=locked_until.isoformat(),
                )
            raise InvalidCredentialsError(
                "Invalid email or password",
                hint="Check your credentials or reset your password",
            )

        await self._user_repo.reset_failed_attempts(user.id)
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
            user_id,
            password_hash=new_hash,
            updated_by_id=updated_by_id,
        )
        return updated  # type: ignore[return-value]

    async def update_profile(
        self,
        user_id: uuid.UUID,
        full_name: str | None = None,
        email: str | None = None,
        username: str | None = None,
        updated_by_id: uuid.UUID | None = None,
    ) -> User:
        """Update user profile information."""
        updates: dict[str, Any] = {}
        if full_name is not None:
            updates["full_name"] = full_name
        if email is not None:
            existing = await self._user_repo.get_by_email(email)
            if existing is not None and existing.id != user_id:
                raise UserAlreadyExistsError(
                    f"Email '{email}' is already in use",
                    hint="Use a different email address",
                )
            updates["email"] = email
            updates["email_verified"] = False
        if username is not None:
            existing = await self._user_repo.get_by_username(username)
            if existing is not None and existing.id != user_id:
                raise UserAlreadyExistsError(
                    f"Username '{username}' is already taken",
                    hint="Choose a different username",
                )
            updates["username"] = username
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
            user_id,
            is_active=True,
            updated_by_id=updated_by_id,
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
        await self.get_by_id(user_id)  # ensure user exists
        new_hash = self._password_manager.hash_password(password)
        updated = await self._user_repo.update(
            user_id,
            password_hash=new_hash,
            updated_by_id=updated_by_id,
        )
        return updated  # type: ignore[return-value]

    async def search_users(
        self,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[User], int]:
        """Search users with pagination."""
        offset = (page - 1) * per_page
        return await self._user_repo.search_users(search, limit=per_page, offset=offset)

    async def admin_update_user(
        self,
        user_id: uuid.UUID,
        email: str | None = None,
        username: str | None = None,
        full_name: str | None = None,
        is_active: bool | None = None,
        updated_by_id: uuid.UUID | None = None,
    ) -> User:
        """Admin update any user's profile. Cannot deactivate a superuser."""
        if is_active is not None and not is_active:
            target = await self._user_repo.get(user_id)
            if target is not None and target.is_superuser:
                raise CannotModifySuperuserError("Cannot deactivate a superuser")

        updates: dict[str, Any] = {}
        if email is not None:
            existing = await self._user_repo.get_by_email(email)
            if existing is not None and existing.id != user_id:
                raise UserAlreadyExistsError(f"Email '{email}' is already in use")
            updates["email"] = email
        if username is not None:
            existing = await self._user_repo.get_by_username(username)
            if existing is not None and existing.id != user_id:
                raise UserAlreadyExistsError(f"Username '{username}' is already taken")
            updates["username"] = username
        if full_name is not None:
            updates["full_name"] = full_name
        if is_active is not None:
            updates["is_active"] = is_active
        updated = await self._user_repo.update(user_id, updated_by_id=updated_by_id, **updates)
        if updated is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return updated

    async def delete_user(
        self,
        user_id: uuid.UUID,
        deleted_by_id: uuid.UUID | None = None,
    ) -> bool:
        """Soft-delete a user. Cannot delete yourself or a superuser."""
        if deleted_by_id is not None and deleted_by_id == user_id:
            raise CannotDeleteSelfError("You cannot delete your own account")
        user = await self.get_by_id(user_id)
        if user.is_superuser:
            raise CannotModifySuperuserError("Cannot delete a superuser")
        return await self._user_repo.delete(
            user_id, deleted_by_id=deleted_by_id, updated_by_id=deleted_by_id
        )

    async def cleanup_expired_users(self) -> int:
        """Hard-delete inactive users whose account expiry has passed."""
        return await self._user_repo.hard_delete_expired_inactive()
