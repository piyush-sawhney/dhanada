"""JWT token management with HS256 symmetric signing and key rotation support."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from dhanada.auth.exceptions import InvalidTokenError, TokenExpiredError


@dataclass
class TokenPayload:
    """Base JWT token payload."""

    sub: str
    """Subject (user UUID)."""

    exp: datetime
    """Expiration time."""

    iat: datetime
    """Issued at time."""

    jti: str
    """JWT ID (unique token identifier)."""

    type: str
    """Token type: 'access' or 'refresh'."""


@dataclass
class AccessTokenPayload(TokenPayload):
    """Access token payload with authorization claims."""

    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


@dataclass
class RefreshTokenPayload(TokenPayload):
    """Refresh token payload with rotation tracking."""

    family_id: str
    """Token family identifier for rotation chain."""


class JWTManager:
    """Manages JWT token creation, verification, and decoding.

    Uses HS256 (HMAC with SHA-256) symmetric signing.
    Access tokens are short-lived (default 15 min).
    Refresh tokens are long-lived (default 7 days) with rotation.

    Supports key rotation: multiple keys identified by a `kid` (Key ID)
    header. The current key is used for signing; all keys (current +
    previous) are accepted for verification, allowing graceful rotation.
    """

    def __init__(
        self,
        secret_key: str,
        key_id: str = "current",
        previous_keys: dict[str, str] | None = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
    ) -> None:
        self._keys: dict[str, str] = {key_id: secret_key, **(previous_keys or {})}
        self._current_key_id = key_id
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_token_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_token_expire_days)

    def create_access_token(
        self,
        user_id: uuid.UUID,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> str:
        """Create a short-lived access token.

        Args:
            user_id: User UUID.
            roles: List of role names for authorization.
            permissions: List of permission strings (e.g., "users:read").

        Returns:
            Signed JWT access token string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "exp": now + self._access_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "access",
            "roles": roles or [],
            "permissions": permissions or [],
        }
        headers = {"kid": self._current_key_id}
        return jwt.encode(
            payload,
            self._keys[self._current_key_id],
            algorithm=self._algorithm,
            headers=headers,
        )

    def create_refresh_token(
        self,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
    ) -> str:
        """Create a long-lived refresh token for rotation.

        Args:
            user_id: User UUID.
            family_id: Token family UUID for rotation chain tracking.

        Returns:
            Signed JWT refresh token string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "exp": now + self._refresh_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "refresh",
            "family_id": str(family_id),
        }
        headers = {"kid": self._current_key_id}
        return jwt.encode(
            payload,
            self._keys[self._current_key_id],
            algorithm=self._algorithm,
            headers=headers,
        )

    def verify_access_token(self, token: str) -> AccessTokenPayload:
        """Verify and decode an access token.

        Args:
            token: JWT access token string.

        Returns:
            AccessTokenPayload with decoded claims.

        Raises:
            TokenExpiredError: Token has expired.
            InvalidTokenError: Token is malformed or signature invalid.
        """
        payload = self._decode_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenError("Token is not an access token")
        return AccessTokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            type=payload["type"],
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
        )

    def verify_refresh_token(self, token: str) -> RefreshTokenPayload:
        """Verify and decode a refresh token.

        Args:
            token: JWT refresh token string.

        Returns:
            RefreshTokenPayload with decoded claims.

        Raises:
            TokenExpiredError: Token has expired.
            InvalidTokenError: Token is malformed or signature invalid.
        """
        payload = self._decode_token(token)
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Token is not a refresh token")
        return RefreshTokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            type=payload["type"],
            family_id=payload["family_id"],
        )

    def create_setup_token(self, user_id: uuid.UUID) -> str:
        """Create a short-lived setup token for first-time login flow.

        Args:
            user_id: User UUID.

        Returns:
            Signed JWT setup token string (15 min expiry).
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=15),
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "setup",
        }
        headers = {"kid": self._current_key_id}
        return jwt.encode(
            payload,
            self._keys[self._current_key_id],
            algorithm=self._algorithm,
            headers=headers,
        )

    def verify_setup_token(self, token: str) -> TokenPayload:
        """Verify and decode a setup token.

        Args:
            token: JWT setup token string.

        Returns:
            TokenPayload with decoded claims.

        Raises:
            TokenExpiredError: Token has expired.
            InvalidTokenError: Token is malformed, signature invalid, or wrong type.
        """
        payload = self._decode_token(token)
        if payload.get("type") != "setup":
            raise InvalidTokenError("Token is not a setup token")
        return TokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            type=payload["type"],
        )

    def create_verification_token(self, user_id: uuid.UUID, ttl_minutes: int = 1440) -> str:
        """Create an email verification token.

        Args:
            user_id: User UUID.
            ttl_minutes: Token TTL in minutes (default 24h).

        Returns:
            Signed JWT verification token string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=ttl_minutes),
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "verify_email",
        }
        headers = {"kid": self._current_key_id}
        return jwt.encode(
            payload,
            self._keys[self._current_key_id],
            algorithm=self._algorithm,
            headers=headers,
        )

    def verify_verification_token(self, token: str) -> TokenPayload:
        """Verify and decode an email verification token.

        Args:
            token: JWT verification token string.

        Returns:
            TokenPayload with decoded claims.

        Raises:
            TokenExpiredError: Token has expired.
            InvalidTokenError: Token is malformed or wrong type.
        """
        payload = self._decode_token(token)
        if payload.get("type") != "verify_email":
            raise InvalidTokenError("Token is not a verification token")
        return TokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            type=payload["type"],
        )

    def create_reset_token(self, user_id: uuid.UUID, ttl_minutes: int = 60) -> str:
        """Create a password reset token (single-use).

        Args:
            user_id: User UUID.
            ttl_minutes: Token TTL in minutes (default 1h).

        Returns:
            Signed JWT reset token string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=ttl_minutes),
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "reset",
        }
        headers = {"kid": self._current_key_id}
        return jwt.encode(
            payload,
            self._keys[self._current_key_id],
            algorithm=self._algorithm,
            headers=headers,
        )

    def verify_reset_token(self, token: str) -> TokenPayload:
        """Verify and decode a password reset token.

        Args:
            token: JWT reset token string.

        Returns:
            TokenPayload with decoded claims.

        Raises:
            TokenExpiredError: Token has expired.
            InvalidTokenError: Token is malformed or wrong type.
        """
        payload = self._decode_token(token)
        if payload.get("type") != "reset":
            raise InvalidTokenError("Token is not a reset token")
        return TokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            type=payload["type"],
        )

    def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Reads the `kid` header to select the correct signing key,
        supporting key rotation with multiple active keys.

        Args:
            token: JWT token string.

        Returns:
            Decoded payload dictionary.
        """
        try:
            # Read the key ID from the unverified header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid", self._current_key_id)
        except JWTError:
            kid = self._current_key_id

        key = self._keys.get(kid)
        if key is None:
            raise InvalidTokenError(f"Unknown signing key: {kid}")

        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[self._algorithm],
                options={
                    "require": ["sub", "exp", "iat", "jti", "type"],
                    "verify_exp": True,
                },
            )
            return payload
        except ExpiredSignatureError:
            raise TokenExpiredError("Token has expired") from None
        except JWTError as e:
            raise InvalidTokenError(f"Invalid token: {e}") from None
