"""Dhanada Auth - User Management & Authentication."""

from dhanada.auth.api import AuthManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.exceptions import (
    AuthenticationError,
    AuthError,
    AuthorizationError,
    CannotDeleteSystemRoleError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    TokenExpiredError,
    TOTPAlreadyEnabledError,
    TOTPError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from dhanada.auth.models import (
    RefreshToken,
    Role,
    RolePermission,
    TOTPSecret,
    User,
)

__all__ = [
    "AuthManager",
    "AuthConfig",
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "CannotDeleteSystemRoleError",
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
