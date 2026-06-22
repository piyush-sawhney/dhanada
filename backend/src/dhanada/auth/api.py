"""AuthManager - High-level authentication facade."""

import secrets
import uuid

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
    SuperuserAlreadyExistsError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
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
        current_user_id: uuid.UUID | None = None,
        is_active: bool = True,
    ) -> User:
        """Register a new user."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            user = await service.register(
                email=email,
                username=username,
                password=password,
                full_name=full_name,
                created_by_id=current_user_id,
            )
            if not is_active:
                await user_repo.update(
                    user.id, is_active=False, updated_by_id=current_user_id,
                )
            return user

    async def verify_credentials(
        self, email: str, password: str,
    ) -> User:
        """Verify email/password credentials and return the user.

        Does NOT check TOTP or is_active status.
        Used by the login endpoint to determine if setup is needed.
        """
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            return await service.authenticate(email, password)

    async def create_superuser(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        """Register the first superuser. Only succeeds when no users exist."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            if await user_repo.count() > 0:
                raise SuperuserAlreadyExistsError(
                    "A superuser already exists — bootstrap is blocked",
                    hint="Login as the existing superuser to manage users",
                )
            service = UserService(user_repo, self._password_manager)
            user = await service.register_superuser(
                email=email,
                username=username,
                password=password,
                full_name=full_name,
            )
            # Self-reference: the superuser is its own creator
            await user_repo.update(user.id, created_by_id=user.id)
            return user

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
        current_user_id: uuid.UUID | None = None,
    ) -> User:
        """Change a user's password."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            user = await service.change_password(
                user_id, old_password, new_password,
                updated_by_id=current_user_id,
            )
            return user

    async def enable_totp(
        self, user_id: uuid.UUID, generate_backup_codes: bool = True,
    ) -> TOTPEnrollmentResult:
        """Enable TOTP for a user."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.enable(user_id, generate_backup_codes=generate_backup_codes)

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
    ) -> list[str]:
        """Generate new backup codes."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.generate_backup_codes(user_id)

    async def assign_role(
        self, user_id: uuid.UUID, role_name: str,
        current_user_id: uuid.UUID | None = None,
    ) -> bool:
        """Assign a role to a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.assign_role(
                user_id, role_name, created_by_id=current_user_id,
            )

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
        current_user_id: uuid.UUID | None = None,
    ) -> User:
        """Update a user's profile."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = UserService(user_repo, self._password_manager)
            return await service.update_profile(
                user_id, full_name=full_name, updated_by_id=current_user_id,
            )

    async def get_user_roles(self, user_id: uuid.UUID) -> list[str]:
        """Get all role names for a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.get_user_roles(user_id)

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[str]:
        """Get all permission strings for a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.get_user_permissions(user_id)

    @property
    def config(self) -> AuthConfig:
        return self._config

    async def _create_tokens(
        self,
        user: User,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Create access and refresh tokens for a user."""
        async with self._db.session() as session:
            token_repo = RefreshTokenRepository(session)
            user_repo = UserRepository(session)
            token_service = TokenService(token_repo, user_repo, self._jwt)

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

    def generate_setup_token(self, user_id: uuid.UUID) -> str:
        """Generate a 15-minute setup token for first-time or reset login."""
        return self._jwt.create_setup_token(user_id)

    async def totp_is_enabled(self, user_id: uuid.UUID) -> bool:
        """Check if TOTP is enabled and verified for a user."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.is_enabled(user_id)

    async def verify_totp(self, user_id: uuid.UUID, token: str) -> bool:
        """Verify a TOTP token or backup code during login."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            return await service.verify(user_id, token)

    async def complete_setup(
        self,
        user_id: uuid.UUID,
        new_password: str,
        current_user_id: uuid.UUID,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Complete first-time setup: set password, activate, issue tokens.

        Requires TOTP to be already verified before proceeding.
        For already-active users (e.g., bootstrap superuser re-login),
        skips password change and activation.
        """
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            totp_repo = TOTPRepository(session)
            user_service = UserService(user_repo, self._password_manager)
            totp_service = TOTPService(totp_repo, user_repo, self._totp_manager)

            # Enforce TOTP verification before completing setup
            if not await totp_service.is_enabled(user_id):
                raise TOTPNotEnabledError(
                    "TOTP must be enabled and verified before completing setup",
                    hint="Call /totp/enable and /totp/verify first",
                )

            user = await user_service.get_by_id(user_id)

            # Only set password and activate for inactive users
            if not user.is_active:
                await user_service.set_password(
                    user_id, new_password, updated_by_id=current_user_id,
                )
                await user_service.activate_user(
                    user_id, updated_by_id=current_user_id,
                )
                user = await user_service.get_by_id(user_id)

            token_service = TokenService(token_repo, user_repo, self._jwt)
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

    async def reset_user_auth(
        self,
        user_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> str:
        """Admin force-reset: disable TOTP, deactivate, set temp password.

        Returns the temporary password string.
        """
        temp_password = self.generate_temp_password()

        async with self._db.session() as session:
            user_repo = UserRepository(session)
            totp_repo = TOTPRepository(session)

            user_service = UserService(user_repo, self._password_manager)
            await user_service.set_password(
                user_id, temp_password, updated_by_id=current_user_id,
            )
            await user_repo.update(
                user_id, is_active=False, updated_by_id=current_user_id,
            )
            await totp_repo.delete_by_user_id(user_id)

        return temp_password

    @staticmethod
    def generate_temp_password() -> str:
        """Generate a secure temporary password."""
        return secrets.token_urlsafe(12)

    async def has_users(self) -> bool:
        """Check if any users exist in the database."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            return await user_repo.count() > 0

    async def close(self) -> None:
        """Close database connections."""
        await self._db.close()
