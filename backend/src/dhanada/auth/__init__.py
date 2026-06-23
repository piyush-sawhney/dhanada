"""Dhanada Auth - User Management & Authentication."""

from dhanada.auth.api import AuthManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthError,
    AuthorizationError,
    CannotDeleteSystemRoleError,
    ConfigurationError,
    EncryptionError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    SuperuserAlreadyExistsError,
    TokenExpiredError,
    TOTPAlreadyEnabledError,
    TOTPError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
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
    "AccountLockedError",
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "CannotDeleteSystemRoleError",
    "ConfigurationError",
    "EncryptionError",
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
    "SuperuserAlreadyExistsError",
    "ValidationError",
    "User",
    "Role",
    "RolePermission",
    "TOTPSecret",
    "RefreshToken",
]

__version__ = "0.1.0"
