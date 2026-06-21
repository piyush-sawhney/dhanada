"""AuthManager - High-level authentication facade."""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.auth.passwords import PasswordManager
from dhanada.auth.auth.totp import TOTPManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.crypto.envelope import EnvelopeEncryption
from dhanada.auth.crypto.keys import KEKManager
from dhanada.auth.db.repository import (
    RefreshTokenRepository,
    RoleRepository,
    TOTPRepository,
    UserRepository,
)
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.exceptions import (
    InvalidCredentialsError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
    UserNotFoundError,
)
from dhanada.auth.models.user import User
from dhanada.auth.services.role_service import PermissionCheck, RoleService
from dhanada.auth.services.token_service import TokenResult, TokenService
from dhanada.auth.services.totp_service import TOTPEnrollmentResult, TOTPService
from dhanada.auth.services.user_service import UserService


class AuthManager:
    """High-level authentication and authorization facade.

    Provides a unified API for:
    - User registration and authentication
    - TOTP 2FA enrollment and verification
    - JWT token management with refresh rotation
    - Role-based permission checking
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config
        self._db = DatabaseSession(str(config.database_url))

        # Initialize crypto
        kek_manager = KEKManager.from_env(config.kek_base64)
        self._envelope = EnvelopeEncryption(kek_manager)

        # Initialize primitives
        self._jwt = JWTManager(
            secret_key=config.jwt_secret_key,
            algorithm=config.jwt_algorithm,
            access_token_expire_minutes=config.jwt_access_token_expire_minutes,
            refresh_token_expire_days=config.jwt_refresh_token_expire_days,
        )
        self._password_manager = PasswordManager(bcrypt_rounds=config.bcrypt_rounds)
        self._totp_manager = TOTPManager(
            encryption=self._envelope,
            issuer=config.totp_issuer,
            window=config.totp_window,
        )

    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        """Register a new user."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            return await service.register(
                email=email,
                username=username,
                password=password,
                full_name=full_name,
            )

    async def authenticate(
        self,
        email: str,
        password: str,
        totp_token: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Authenticate with email/password and optional TOTP.

        Returns tokens on success. If TOTP is enabled, requires a valid token.
        """
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            totp_repo = TOTPRepository(session)
            role_repo = RoleRepository(session)

            user_service = UserService(user_repo, self._password_manager)
            totp_service = TOTPService(totp_repo, user_repo, self._totp_manager)
            token_service = TokenService(token_repo, user_repo, self._jwt)

            user = await user_service.authenticate(email, password)

            # Check TOTP if enabled
            if await totp_service.is_enabled(user.id):
                if totp_token is None:
                    raise TOTPNotEnabledError(
                        "TOTP code required",
                        hint="Provide your authenticator app code to complete login",
                    )
                if not await totp_service.verify(user.id, totp_token):
                    raise TOTPInvalidTokenError("Invalid TOTP code")

            await user_service.update_last_login(user.id)

            roles = [role.name for role in user.roles]
            permissions: list[str] = []
            for role in user.roles:
                for perm in role.permissions:
                    permissions.append(f"{perm.resource}:{perm.action}")

            return await token_service.create_tokens(
                user_id=user.id,
                roles=roles,
                permissions=permissions,
                user_agent=user_agent,
                ip_address=ip_address,
            )

    async def refresh_session(
        self,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Refresh an access token using a refresh token (with rotation)."""
        async with self._db.session() as session:
            token_repo = RefreshTokenRepository(session)
            user_repo = UserRepository(session)
            service = TokenService(token_repo, user_repo, self._jwt)
            return await service.refresh_tokens(
                refresh_token=refresh_token,
                user_agent=user_agent,
                ip_address=ip_address,
            )

    async def revoke_session(self, refresh_token: str) -> bool:
        """Revoke a specific refresh token."""
        async with self._db.session() as session:
            token_repo = RefreshTokenRepository(session)
            user_repo = UserRepository(session)
            service = TokenService(token_repo, user_repo, self._jwt)
            return await service.revoke_token(refresh_token)

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user."""
        async with self._db.session() as session:
            token_repo = RefreshTokenRepository(session)
            user_repo = UserRepository(session)
            service = TokenService(token_repo, user_repo, self._jwt)
            return await service.revoke_all_user_tokens(user_id)

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Get a user by ID."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            return await service.get_by_id(user_id)

    async def change_password(
        self,
        user_id: uuid.UUID,
        old_password: str,
        new_password: str,
    ) -> User:
        """Change a user's password."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            user = await service.change_password(user_id, old_password, new_password)
            return user

    async def enable_totp(self, user_id: uuid.UUID) -> TOTPEnrollmentResult:
        """Enable TOTP for a user."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.enable(user_id)

    async def verify_and_confirm_totp(
        self, user_id: uuid.UUID, token: str
    ) -> bool:
        """Verify and confirm TOTP enrollment."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.verify_and_confirm(user_id, token)

    async def disable_totp(self, user_id: uuid.UUID, token: str) -> bool:
        """Disable TOTP for a user."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.disable(user_id, token)

    async def generate_backup_codes(
        self, user_id: uuid.UUID
    ) -> List[str]:
        """Generate new backup codes."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.generate_backup_codes(user_id)

    async def assign_role(self, user_id: uuid.UUID, role_name: str) -> bool:
        """Assign a role to a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.assign_role(user_id, role_name)

    async def revoke_role(self, user_id: uuid.UUID, role_name: str) -> bool:
        """Revoke a role from a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.revoke_role(user_id, role_name)

    async def check_permission(
        self, user_id: uuid.UUID, resource: str, action: str
    ) -> PermissionCheck:
        """Check if a user has a specific permission."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.check_permission(user_id, resource, action)

    async def update_profile(
        self,
        user_id: uuid.UUID,
        full_name: str | None = None,
    ) -> User:
        """Update a user's profile."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            return await service.update_profile(user_id, full_name=full_name)

    async def get_user_roles(self, user_id: uuid.UUID) -> List[str]:
        """Get all role names for a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.get_user_roles(user_id)

    async def get_user_permissions(self, user_id: uuid.UUID) -> List[str]:
        """Get all permission strings for a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.get_user_permissions(user_id)

    @property
    def config(self) -> AuthConfig:
        return self._config

    async def close(self) -> None:
        """Close database connections."""
        await self._db.close()