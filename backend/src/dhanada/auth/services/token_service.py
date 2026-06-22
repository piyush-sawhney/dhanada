"""Token management service with refresh token rotation."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.db.repository import RefreshTokenRepository, UserRepository
from dhanada.auth.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    UserNotFoundError,
)


@dataclass
class TokenResult:
    """Result of token creation or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int = 900  # seconds


class TokenService:
    """Token creation, refresh, and revocation with rotation."""

    def __init__(
        self,
        token_repo: RefreshTokenRepository,
        user_repo: UserRepository,
        jwt_manager: JWTManager,
        access_token_ttl: int = 900,
    ) -> None:
        self._token_repo = token_repo
        self._user_repo = user_repo
        self._jwt_manager = jwt_manager
        self._access_token_ttl = access_token_ttl

    async def create_tokens(
        self,
        user_id: uuid.UUID,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Create access and refresh tokens for a user.

        Args:
            user_id: User UUID.
            roles: User's role names for access token claims.
            permissions: User's permission strings for access token claims.
            user_agent: Client user agent for audit tracking.
            ip_address: Client IP address for audit tracking.

        Returns:
            TokenResult with access token, refresh token, and metadata.
        """
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        family_id = uuid.uuid4()

        # Create JWT tokens
        access_token = self._jwt_manager.create_access_token(
            user_id=user_id,
            roles=roles or [],
            permissions=permissions or [],
        )
        refresh_token = self._jwt_manager.create_refresh_token(
            user_id=user_id,
            family_id=family_id,
        )

        # Store refresh token hash for rotation tracking
        token_hash = self._hash_token(refresh_token)

        await self._token_repo.create(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(UTC) + self._jwt_manager._refresh_expire,
        )

        return TokenResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._access_token_ttl,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResult:
        """Refresh tokens using a valid refresh token (rotation).

        Implements refresh token rotation:
        1. Verify the refresh token JWT
        2. Look up the stored hash
        3. Mark old token as replaced
        4. Issue new tokens in the same family
        5. If token was already replaced → revoke entire family (replay detection)

        Args:
            refresh_token: Current refresh token string.
            user_agent: Client user agent.
            ip_address: Client IP address.

        Returns:
            TokenResult with new tokens.
        """
        try:
            payload = self._jwt_manager.verify_refresh_token(refresh_token)
        except TokenExpiredError:
            raise InvalidTokenError(
                "Refresh token expired, please log in again",
                hint="Use your credentials to get a new session",
            ) from None

        user_id = uuid.UUID(payload.sub)
        family_id = uuid.UUID(payload.family_id)
        token_hash = self._hash_token(refresh_token)

        stored_token = await self._token_repo.get_by_token_hash(token_hash)
        if stored_token is None:
            raise InvalidTokenError("Refresh token not found or revoked")

        if stored_token.is_revoked:
            raise InvalidTokenError("Refresh token has been revoked")

        # Replay detection: if token was already replaced, revoke entire family
        if stored_token.is_replaced:
            await self._token_repo.revoke_family(family_id)
            raise InvalidTokenError(
                "Refresh token reuse detected, all family tokens revoked",
                hint="Please log in again with your credentials",
            )

        # Get user roles and permissions for new access token
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        roles = [role.name for role in user.roles]
        perm_list: list[str] = []
        for role in user.roles:
            for perm in role.permissions:
                perm_list.append(f"{perm.resource}:{perm.action}")

        # Mark old token as replaced
        await self._token_repo.update(
            stored_token.id,
            replaced_at=datetime.now(UTC),
        )

        # Create new tokens in the same family
        new_access = self._jwt_manager.create_access_token(
            user_id=user_id,
            roles=roles,
            permissions=perm_list,
        )
        new_refresh = self._jwt_manager.create_refresh_token(
            user_id=user_id,
            family_id=family_id,
        )

        # Store new refresh token
        new_hash = self._hash_token(new_refresh)
        await self._token_repo.create(
            user_id=user_id,
            token_hash=new_hash,
            family_id=family_id,
            parent_token_hash=token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(UTC) + self._jwt_manager._refresh_expire,
        )

        return TokenResult(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=self._access_token_ttl,
        )

    async def revoke_token(self, refresh_token: str) -> bool:
        """Revoke a specific refresh token."""
        token_hash = self._hash_token(refresh_token)
        stored = await self._token_repo.get_by_token_hash(token_hash)
        if stored is None or stored.is_revoked:
            return False
        await self._token_repo.update(stored.id, revoked_at=datetime.now(UTC))
        return True

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user."""
        return await self._token_repo.revoke_user_tokens(user_id)

    def _hash_token(self, token: str) -> str:
        """Hash a refresh token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()
