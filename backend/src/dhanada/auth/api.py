"""AuthManager - High-level authentication facade."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.auth.passwords import PasswordManager
from dhanada.auth.auth.totp import TOTPManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.crypto.envelope import EnvelopeEncryption
from dhanada.auth.crypto.keys import KEKManager
from dhanada.auth.db.repository import (
    AppRepository,
    RefreshTokenRepository,
    RoleRepository,
    TOTPRepository,
    UserRepository,
)
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.email.sender import EmailSender
from dhanada.auth.exceptions import (
    AuthenticationError,
    CannotModifySuperuserError,
    SuperuserAlreadyExistsError,
    TOTPError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
    UserNotFoundError,
)
from dhanada.auth.models.app import App
from dhanada.auth.models.role import Role
from dhanada.auth.models.user import User
from dhanada.auth.services.audit_service import AuditService
from dhanada.auth.services.password_reset_service import (
    PasswordResetResult,
    PasswordResetService,
)
from dhanada.auth.services.recovery_service import RecoveryService
from dhanada.auth.services.role_service import PermissionCheck, RoleService
from dhanada.auth.services.token_service import TokenResult, TokenService
from dhanada.auth.services.totp_service import TOTPEnrollmentResult, TOTPService
from dhanada.auth.services.user_service import UserService
from dhanada.auth.services.verification_service import VerificationResult, VerificationService


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
        kek_manager = KEKManager.from_env(
            config.kek_base64,
            previous_base64_keys=config.kek_previous_base64_keys,
        )
        self._envelope = EnvelopeEncryption(kek_manager)

        # Initialize primitives
        previous_keys = {}
        for i, key in enumerate(config.jwt_previous_secret_keys):
            previous_keys[f"previous_{i}"] = key
        self._jwt = JWTManager(
            secret_key=config.jwt_secret_key,
            key_id=config.jwt_key_id,
            previous_keys=previous_keys or None,
            algorithm=config.jwt_algorithm,
            access_token_expire_minutes=config.jwt_access_token_expire_minutes,
            refresh_token_expire_days=config.jwt_refresh_token_expire_days,
        )
        self._password_manager = PasswordManager()
        self._lockout_threshold = config.account_lockout_threshold
        self._lockout_minutes = config.account_lockout_minutes
        self._email_sender = EmailSender(config)
        self._verification_token_ttl = config.email_verification_token_ttl_minutes
        self._totp_manager = TOTPManager(
            encryption=self._envelope,
            issuer=config.totp_issuer,
            window=config.totp_window,
        )

    def _create_user_service(self, user_repo: UserRepository) -> UserService:
        return UserService(
            user_repo,
            self._password_manager,
            lockout_threshold=self._lockout_threshold,
            lockout_minutes=self._lockout_minutes,
        )

    async def register_user(
        self,
        email: str,
        username: str | None = None,
        password: str = "",
        full_name: str | None = None,
        current_user_id: uuid.UUID | None = None,
        is_active: bool = True,
        ip_address: str | None = None,
    ) -> User:
        """Register a new user."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            user = await service.register(
                email=email,
                username=username,
                password=password,
                full_name=full_name,
                created_by_id=current_user_id,
            )
            if not is_active:
                await user_repo.update(
                    user.id,
                    is_active=False,
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                    updated_by_id=current_user_id,
                )
            AuditService.user_created(
                user_id=str(user.id),
                actor_id=str(current_user_id) if current_user_id else None,
                ip_address=ip_address,
            )
            return user

    async def verify_credentials(
        self,
        email: str,
        password: str,
    ) -> User:
        """Verify email/password credentials and return the user.

        Does NOT check TOTP or is_active status.
        Used by the login endpoint to determine if setup is needed.
        """
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            return await service.authenticate(email, password)

    async def create_superuser(
        self,
        email: str,
        username: str | None = None,
        password: str = "",
        full_name: str | None = None,
        ip_address: str | None = None,
    ) -> User:
        """Register the first superuser. Only succeeds when no users exist."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            if await user_repo.count() > 0:
                raise SuperuserAlreadyExistsError(
                    "A superuser already exists — bootstrap is blocked",
                    hint="Login as the existing superuser to manage users",
                )
            service = self._create_user_service(user_repo)
            user = await service.register_superuser(
                email=email,
                username=username,
                password=password,
                full_name=full_name,
            )
            # Self-reference: the superuser is its own creator
            await user_repo.update(user.id, created_by_id=user.id)
            # Mark inactive with 24h expiry so login forces TOTP setup flow
            await user_repo.update(
                user.id,
                is_active=False,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
                updated_by_id=user.id,
            )
            # Auto-register superuser to all apps
            app_repo = AppRepository(session)
            apps = await app_repo.list_all()
            for app in apps:
                await app_repo.assign_user(
                    user.id, app.id, assigned_by_id=user.id, created_by_id=user.id
                )

            AuditService.bootstrap_complete(
                user_id=str(user.id),
                ip_address=ip_address,
            )
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

            user_service = self._create_user_service(user_repo)
            totp_service = TOTPService(totp_repo, user_repo, self._totp_manager)
            token_service = TokenService(token_repo, user_repo, self._jwt)

            user = await user_service.authenticate(email, password)

            AuditService.login_success(
                user_id=str(user.id),
                ip_address=ip_address,
            )

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

    async def get_user_sessions(
        self,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get list of active sessions for a user (metadata only)."""
        async with self._db.session() as session:
            token_repo = RefreshTokenRepository(session)
            user_repo = UserRepository(session)
            service = TokenService(token_repo, user_repo, self._jwt)
            return await service.get_user_sessions(user_id)

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Get a user by ID."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            return await service.get_by_id(user_id)

    async def change_password(
        self,
        user_id: uuid.UUID,
        old_password: str,
        new_password: str,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> User:
        """Change a user's password."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            user = await service.change_password(
                user_id,
                old_password,
                new_password,
                updated_by_id=current_user_id,
            )
            AuditService.password_changed(
                user_id=str(user_id),
                actor_id=str(current_user_id) if current_user_id else None,
                ip_address=ip_address,
            )
            return user

    async def enable_totp(
        self,
        user_id: uuid.UUID,
        generate_backup_codes: bool = True,
        current_user_id: uuid.UUID | None = None,
    ) -> TOTPEnrollmentResult:
        """Enable TOTP for a user."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            result = await service.enable(user_id, generate_backup_codes=generate_backup_codes)
            if current_user_id is not None:
                await user_repo.update(user_id, updated_by_id=current_user_id)
            return result

    async def verify_and_confirm_totp(
        self, user_id: uuid.UUID, token: str, current_user_id: uuid.UUID | None = None
    ) -> bool:
        """Verify and confirm TOTP enrollment."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            result = await service.verify_and_confirm(user_id, token)
            if result and current_user_id is not None:
                await user_repo.update(user_id, updated_by_id=current_user_id)
            return result

    async def disable_totp(
        self, user_id: uuid.UUID, token: str, current_user_id: uuid.UUID | None = None
    ) -> bool:
        """Disable TOTP for a user."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            result = await service.disable(user_id, token)
            if result and current_user_id is not None:
                await user_repo.update(user_id, updated_by_id=current_user_id)
            return result

    async def generate_backup_codes(
        self, user_id: uuid.UUID, current_user_id: uuid.UUID | None = None
    ) -> list[str]:
        """Generate new backup codes."""
        async with self._db.session() as session:
            totp_repo = TOTPRepository(session)
            user_repo = UserRepository(session)
            service = TOTPService(totp_repo, user_repo, self._totp_manager)
            result = await service.generate_backup_codes(user_id)
            if current_user_id is not None:
                await user_repo.update(user_id, updated_by_id=current_user_id)
            return result

    async def assign_role(
        self,
        user_id: uuid.UUID,
        role_name: str,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Assign a role to a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            result = await service.assign_role(
                user_id,
                role_name,
                created_by_id=current_user_id,
            )
            AuditService.role_assigned(
                user_id=str(user_id),
                role_name=role_name,
                actor_id=str(current_user_id) if current_user_id else None,
                ip_address=ip_address,
            )
            return result

    async def revoke_role(
        self,
        user_id: uuid.UUID,
        role_name: str,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Revoke a role from a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            result = await service.revoke_role(user_id, role_name)
            AuditService.role_revoked(
                user_id=str(user_id),
                role_name=role_name,
                actor_id=str(current_user_id) if current_user_id else None,
                ip_address=ip_address,
            )
            return result

    async def check_permission(
        self, user_id: uuid.UUID, resource: str, action: str
    ) -> PermissionCheck:
        """Check if a user has a specific permission."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            app_repo = AppRepository(session)
            service = RoleService(role_repo, user_repo, app_repo=app_repo)
            return await service.check_permission(user_id, resource, action)

    async def assert_permission(self, user_id: uuid.UUID, resource: str, action: str) -> None:
        """Assert that a user has a permission, raising if denied."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            app_repo = AppRepository(session)
            service = RoleService(role_repo, user_repo, app_repo=app_repo)
            await service.assert_permission(user_id, resource, action)

    async def update_profile(
        self,
        user_id: uuid.UUID,
        full_name: str | None = None,
        email: str | None = None,
        username: str | None = None,
        current_user_id: uuid.UUID | None = None,
        _ip_address: str | None = None,
    ) -> User:
        """Update a user's profile."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            return await service.update_profile(
                user_id,
                full_name=full_name,
                email=email,
                username=username,
                updated_by_id=current_user_id,
            )

    async def search_users(
        self,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[User], int]:
        """Search users with pagination."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            return await service.search_users(search, page, per_page)

    async def admin_update_user(
        self,
        user_id: uuid.UUID,
        email: str | None = None,
        username: str | None = None,
        full_name: str | None = None,
        is_active: bool | None = None,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> User:
        """Admin update any user's profile."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            user = await service.admin_update_user(
                user_id,
                email=email,
                username=username,
                full_name=full_name,
                is_active=is_active,
                updated_by_id=current_user_id,
            )
            AuditService.user_updated(
                user_id=str(user_id),
                actor_id=str(current_user_id) if current_user_id else None,
                ip_address=ip_address,
            )
            return user

    async def delete_user(
        self,
        user_id: uuid.UUID,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Soft-delete a user and revoke all sessions."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            result = await service.delete_user(user_id, deleted_by_id=current_user_id)
            await self.revoke_all_sessions(user_id)
            AuditService.user_deleted(
                user_id=str(user_id),
                actor_id=str(current_user_id) if current_user_id else None,
                ip_address=ip_address,
            )
            return result

    async def get_user_roles(self, user_id: uuid.UUID) -> list[str]:
        """Get all role names for a user."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.get_user_roles(user_id)

    async def create_role(
        self,
        name: str,
        description: str | None = None,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> Role | None:
        """Create a new role. Returns None if the role already exists."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            role = await service.create_role(name, description)
            if role is not None:
                await session.refresh(role, ["permissions"])
                AuditService.role_created(
                    role_name=name,
                    actor_id=str(current_user_id) if current_user_id else None,
                    ip_address=ip_address,
                )
            return role

    async def get_role_by_name(self, name: str) -> Role | None:
        """Get a role by name."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            role = await service.get_role_by_name(name)
            if role is not None:
                await session.refresh(role, ["permissions"])
            return role

    async def list_roles(self) -> list[Role]:
        """List all roles."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            roles = await service.list_roles()
            for role in roles:
                await session.refresh(role, ["permissions"])
            return roles

    async def delete_role(
        self,
        role_id: uuid.UUID,
        current_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Delete a role."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            result = await service.delete_role(role_id)
            if result:
                AuditService.role_deleted(
                    role_id=str(role_id),
                    actor_id=str(current_user_id) if current_user_id else None,
                    ip_address=ip_address,
                )
            return result

    async def add_permission_to_role(
        self,
        role_name: str,
        resource: str,
        action: str,
        current_user_id: uuid.UUID | None = None,
    ) -> bool:
        """Add a permission to a role."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.add_permission(
                role_name, resource, action, created_by_id=current_user_id
            )

    async def remove_permission_from_role(
        self,
        role_name: str,
        resource: str,
        action: str,
        _current_user_id: uuid.UUID | None = None,
    ) -> bool:
        """Remove a permission from a role."""
        async with self._db.session() as session:
            role_repo = RoleRepository(session)
            user_repo = UserRepository(session)
            service = RoleService(role_repo, user_repo)
            return await service.remove_permission(role_name, resource, action)

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

    @property
    def envelope(self) -> EnvelopeEncryption:
        """Public access to the envelope encryption instance."""
        return self._envelope

    async def _create_tokens(
        self,
        user_id: uuid.UUID,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Create access and refresh tokens for a user.

        Reloads the user within the session to ensure all relationships
        (roles, permissions) are accessible without detached-instance errors.
        """
        async with self._db.session() as session:
            token_repo = RefreshTokenRepository(session)
            user_repo = UserRepository(session)
            token_service = TokenService(token_repo, user_repo, self._jwt)

            fresh_user = await user_repo.get(user_id)
            if fresh_user is None:
                raise UserNotFoundError(f"User {user_id} not found")

            await user_repo.update_last_login(user_id)

            roles = [role.name for role in fresh_user.roles]
            permissions: list[str] = []
            for role in fresh_user.roles:
                for perm in role.permissions:
                    permissions.append(f"{perm.resource}:{perm.action}")

            return await token_service.create_tokens(
                user_id=user_id,
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
            user_service = self._create_user_service(user_repo)
            totp_service = TOTPService(totp_repo, user_repo, self._totp_manager)

            # Enforce TOTP verification before completing setup
            if not await totp_service.is_enabled(user_id):
                raise TOTPNotEnabledError(
                    "TOTP must be enabled and verified before completing setup",
                    hint="Call /totp/enable and /totp/verify first",
                )

            user = await user_service.get_by_id(user_id)

            # Only activate for inactive users; set password if provided
            if not user.is_active:
                if new_password:
                    await user_service.set_password(
                        user_id,
                        new_password,
                        updated_by_id=current_user_id,
                    )
                await user_service.activate_user(
                    user_id,
                    updated_by_id=current_user_id,
                )
                await user_repo.update(
                    user_id,
                    expires_at=None,
                    updated_by_id=current_user_id,
                )
                AuditService.password_changed(
                    user_id=str(user_id),
                    actor_id=str(current_user_id),
                    ip_address=ip_address,
                )
                user = await user_service.get_by_id(user_id)

            await user_service.update_last_login(user_id)
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
        ip_address: str | None = None,
    ) -> str:
        """Admin force-reset: disable TOTP, deactivate, set temp password.

        Cannot reset authentication for a superuser.
        Returns the temporary password string.
        """
        temp_password = self.generate_temp_password()

        async with self._db.session() as session:
            user_repo = UserRepository(session)

            target_user = await user_repo.get(user_id)
            if target_user is not None and target_user.is_superuser:
                raise CannotModifySuperuserError(
                    "Cannot reset authentication for a superuser"
                )
            totp_repo = TOTPRepository(session)

            user_service = self._create_user_service(user_repo)
            await user_service.set_password(
                user_id,
                temp_password,
                updated_by_id=current_user_id,
            )
            await user_repo.update(
                    user_id,
                    is_active=False,
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                    updated_by_id=current_user_id,
                )
            await totp_repo.delete_by_user_id(user_id)

        AuditService.account_reset(
            user_id=str(user_id),
            actor_id=str(current_user_id),
            ip_address=ip_address,
        )
        await self.revoke_all_sessions(user_id)
        return temp_password

    async def resend_welcome(
        self,
        user_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> str:
        """Re-send welcome email with fresh temp password and verification link.

        Lighter than reset_user_auth: does NOT delete TOTP or revoke sessions.
        Only updates the password hash and expiry, then sends a new welcome email.
        """
        temp_password = self.generate_temp_password()

        async with self._db.session() as session:
            user_repo = UserRepository(session)
            target_user = await user_repo.get(user_id)
            if target_user is None:
                raise UserNotFoundError(f"User {user_id} not found")
            if target_user.is_superuser:
                raise CannotModifySuperuserError(
                    "Cannot resend welcome email for a superuser"
                )

            user_service = self._create_user_service(user_repo)
            await user_service.set_password(
                user_id,
                temp_password,
                updated_by_id=current_user_id,
            )
            await user_repo.update(
                user_id,
                is_active=False,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                updated_by_id=current_user_id,
            )

        await self.send_welcome_email(user_id, temp_password)
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

    async def request_recovery(
        self,
        user: User,
    ) -> bool:
        """Send a recovery approval email when a backup code is used.

        Args:
            user: The user who entered a backup code.

        Returns:
            True if the email was sent.
        """
        if not user.is_superuser:
            return False
        if not user.email_verified:
            return False
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            totp_repo = TOTPRepository(session)
            service = RecoveryService(
                jwt_manager=self._jwt,
                user_repo=user_repo,
                totp_repo=totp_repo,
                email_sender=self._email_sender,
                base_url=self._config.base_url,
            )
            return await service.request_recovery(user)

    async def request_recovery_with_password(
        self,
        email: str,
        password: str,
    ) -> bool:
        """Send a recovery approval email when the user has lost TOTP access.

        Verifies credentials first, then sends the recovery email.
        Used by the 'Lost authenticator?' flow on the TOTP step.

        Args:
            email: User's email.
            password: User's password.

        Returns:
            True if the email was sent.

        Raises:
            AuthenticationError: Invalid credentials.
            TOTPError: TOTP is not enabled.
        """
        user = await self.verify_credentials(email, password)
        if not user.is_superuser:
            raise AuthenticationError(
                "Only superusers can self-recover. Contact a superuser to"
                " reset your authentication.",
            )
        if not user.email_verified:
            raise AuthenticationError(
                "Email is not verified. Please verify your email address first."
            )
        if not user.is_active:
            raise AuthenticationError(
                "Account is not active",
                hint="Contact an administrator to reactivate your account.",
            )
        if not await self.totp_is_enabled(user.id):
            raise TOTPError(
                "TOTP is not enabled for this account",
                hint="You can log in without two-factor authentication.",
            )
        return await self.request_recovery(user)

    async def approve_recovery(self, token: str) -> str:
        """Approve recovery after email link click.

        Deletes TOTP, deactivates user, and returns a setup token.

        Args:
            token: Recovery approval JWT from the email link.

        Returns:
            A setup token string.

        Raises:
            InvalidTokenError: Token is invalid or expired.
        """
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            totp_repo = TOTPRepository(session)
            service = RecoveryService(
                jwt_manager=self._jwt,
                user_repo=user_repo,
                totp_repo=totp_repo,
                email_sender=self._email_sender,
                base_url=self._config.base_url,
            )
            return await service.approve_recovery(token)

    async def request_password_reset(self, email: str) -> bool:
        """Request a password reset email. Always returns True (prevents enumeration)."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            service = PasswordResetService(
                jwt_manager=self._jwt,
                user_repo=user_repo,
                password_manager=self._password_manager,
                token_repo=token_repo,
                email_sender=self._email_sender,
                base_url=self._config.base_url,
                token_ttl_minutes=self._config.password_reset_token_ttl_minutes,
            )
            return await service.request_reset(email)

    async def reset_password(
        self,
        token: str,
        new_password: str,
    ) -> PasswordResetResult:
        """Reset a password using a valid reset token.

        Does NOT affect TOTP or account active status.
        Revokes all existing sessions.
        Token is single-use.
        """
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            service = PasswordResetService(
                jwt_manager=self._jwt,
                user_repo=user_repo,
                password_manager=self._password_manager,
                token_repo=token_repo,
                base_url=self._config.base_url,
                token_ttl_minutes=self._config.password_reset_token_ttl_minutes,
            )
            return await service.reset_password(token, new_password)

    async def cleanup_expired_users(self) -> int:
        """Hard-delete inactive users whose account expiry has passed."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = self._create_user_service(user_repo)
            return await service.cleanup_expired_users()

    async def verify_email(self, token: str) -> VerificationResult:
        """Verify a user's email address using a verification token."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = VerificationService(
                jwt_manager=self._jwt,
                user_repo=user_repo,
                base_url=self._config.base_url,
                token_ttl_minutes=self._verification_token_ttl,
            )
            return await service.verify(token)

    async def send_verification_email(self, user_id: uuid.UUID) -> bool:
        """Send a verification email to a user."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            service = VerificationService(
                jwt_manager=self._jwt,
                user_repo=user_repo,
                email_sender=self._email_sender,
                token_ttl_minutes=self._verification_token_ttl,
                base_url=self._config.base_url,
            )
            return await service.send_verification(user_id)

    async def send_temporary_password_email(
        self, user_id: uuid.UUID, temporary_password: str
    ) -> bool:
        """Send a temporary password to a user via email."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get(user_id)
            if user is None or self._email_sender is None:
                return False
            return await self._email_sender.send_temporary_password_email(
                to=user.email,
                full_name=user.full_name,
                temporary_password=temporary_password,
            )

    async def send_welcome_email(
        self, user_id: uuid.UUID, temporary_password: str
    ) -> bool:
        """Send a combined welcome email with temp password and verification link."""
        async with self._db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get(user_id)
            if user is None or self._email_sender is None:
                return False
            token = self._jwt.create_verification_token(
                user_id, self._verification_token_ttl
            )
            verification_url = f"{self._config.base_url}/verify-email?token={token}"
            return await self._email_sender.send_welcome_email(
                to=user.email,
                full_name=user.full_name,
                temporary_password=temporary_password,
                verification_url=verification_url,
            )

    async def register_user_to_app(
        self,
        user_id: uuid.UUID,
        app_slug: str,
        *,
        assigned_by_id: uuid.UUID | None = None,
    ) -> bool:
        """Register a user to an app. Raises if app slug not found."""
        async with self._db.session() as session:
            app_repo = AppRepository(session)
            app = await app_repo.get_by_slug(app_slug)
            if app is None:
                return False
            await app_repo.assign_user(
                user_id, app.id, assigned_by_id=assigned_by_id, created_by_id=assigned_by_id
            )
            return True

    async def unregister_user_from_app(
        self, user_id: uuid.UUID, app_slug: str, _current_user_id: uuid.UUID | None = None
    ) -> bool:
        """Unregister a user from an app."""
        async with self._db.session() as session:
            app_repo = AppRepository(session)
            app = await app_repo.get_by_slug(app_slug)
            if app is None:
                return False
            return await app_repo.remove_user(user_id, app.id)

    async def get_user_apps(self, user_id: uuid.UUID) -> list[App]:
        """Get all apps a user is registered to."""
        async with self._db.session() as session:
            app_repo = AppRepository(session)
            return await app_repo.get_user_apps(user_id)

    async def get_all_apps(self) -> list[App]:
        """Get all registered apps."""
        async with self._db.session() as session:
            return await AppRepository(session).list_all()

    async def close(self) -> None:
        """Close database connections."""
        await self._db.close()
