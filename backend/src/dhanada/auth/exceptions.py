"""Authentication exceptions."""


class AuthError(Exception):
    """Base authentication error."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message} (Hint: {self.hint})"
        return self.message


class AuthenticationError(AuthError):
    """Authentication failed."""


class AuthorizationError(AuthError):
    """Authorization failed - insufficient permissions."""


class InvalidTokenError(AuthError):
    """Token is invalid or malformed."""


class TokenExpiredError(AuthError):
    """Token has expired."""


class UserNotFoundError(AuthError):
    """User not found."""


class UserAlreadyExistsError(AuthError):
    """User already exists."""


class InvalidCredentialsError(AuthError):
    """Invalid username/email or password."""


class TOTPError(AuthError):
    """TOTP-related error."""


class TOTPInvalidTokenError(TOTPError):
    """Invalid TOTP token."""


class TOTPAlreadyEnabledError(TOTPError):
    """TOTP already enabled for user."""


class TOTPNotEnabledError(TOTPError):
    """TOTP not enabled for user."""


class PermissionDeniedError(AuthorizationError):
    """Permission denied for resource/action."""


class EncryptionError(AuthError):
    """Encryption/decryption error."""


class ConfigurationError(AuthError):
    """Configuration error."""