"""JWT token management with HS256 symmetric signing."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, List

from jose import JWTError, jwt

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

    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)


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
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_token_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_token_expire_days)

    def create_access_token(
        self,
        user_id: uuid.UUID,
        roles: List[str] | None = None,
        permissions: List[str] | None = None,
    ) -> str:
        """Create a short-lived access token.

        Args:
            user_id: User UUID.
            roles: List of role names for authorization.
            permissions: List of permission strings (e.g., "users:read").

        Returns:
            Signed JWT access token string.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": now + self._access_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "access",
            "roles": roles or [],
            "permissions": permissions or [],
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

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
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": now + self._refresh_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "refresh",
            "family_id": str(family_id),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

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

    def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: JWT token string.

        Returns:
            Decoded payload dictionary.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={
                    "require": ["sub", "exp", "iat", "jti", "type"],
                    "verify_exp": True,
                },
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except JWTError as e:
            raise InvalidTokenError(f"Invalid token: {e}")