"""Dhanada Auth - User Management & Authentication."""

from dhanada.auth.api import AuthManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.exceptions import (
    AuthError,
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    TokenExpiredError,
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    TOTPError,
    TOTPInvalidTokenError,
    TOTPAlreadyEnabledError,
    TOTPNotEnabledError,
    PermissionDeniedError,
)

from dhanada.auth.models import (
    User,
    Role,
    RolePermission,
    TOTPSecret,
    RefreshToken,
)

__all__ = [
    "AuthManager",
    "AuthConfig",
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "InvalidTokenError",
    "TokenExpiredError",
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "InvalidCredentialsError",
    "TOTPError",
    "TOTPInvalidTokenError",
    "TOTPAlreadyEnabledError",
    "TOTPNotEnabledError",
    "PermissionDeniedError",
    "User",
    "Role",
    "RolePermission",
    "TOTPSecret",
    "RefreshToken",
]

__version__ = "0.1.0"