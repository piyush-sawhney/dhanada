"""Password reset service for self-service password recovery."""

import uuid
from dataclasses import dataclass

from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.auth.passwords import PasswordManager
from dhanada.auth.db.repository import RefreshTokenRepository, UserRepository
from dhanada.auth.email.sender import EmailSender
from dhanada.auth.exceptions import InvalidTokenError, TokenExpiredError, UserNotFoundError


@dataclass
class PasswordResetResult:
    """Result of a password reset operation."""

    success: bool
    message: str = "Password has been reset successfully."


class PasswordResetService:
    """Password reset token generation and confirmation.

    Tokens are single-use JWT tokens (type='reset') that are invalidated
    after successful password reset. All existing sessions are revoked
    upon reset to prevent unauthorized access.
    """

    def __init__(
        self,
        jwt_manager: JWTManager,
        user_repo: UserRepository,
        password_manager: PasswordManager,
        token_repo: RefreshTokenRepository,
        base_url: str,
        token_ttl_minutes: int,
        email_sender: EmailSender | None = None,
    ) -> None:
        self._jwt = jwt_manager
        self._user_repo = user_repo
        self._password_manager = password_manager
        self._token_repo = token_repo
        self._email_sender = email_sender
        self._base_url = base_url
        self._token_ttl = token_ttl_minutes

    async def request_reset(self, email: str) -> bool:
        """Request a password reset.

        Generates a reset token and sends it via email.
        Always returns True to prevent email enumeration.

        Args:
            email: User's email address.

        Returns:
            Always True (to prevent email enumeration).
        """
        user = await self._user_repo.get_by_email(email)
        if user is None or user.deleted_at is not None:
            return True

        token = self._jwt.create_reset_token(user.id, self._token_ttl)
        reset_url = f"{self._base_url}/reset-password?token={token}"

        if self._email_sender is not None:
            await self._email_sender.send_password_reset_email(
                to=user.email,
                username=user.username,
                reset_url=reset_url,
            )

        return True

    async def reset_password(self, token: str, new_password: str) -> PasswordResetResult:
        """Reset a user's password using a valid reset token.

        Token is single-use: it becomes invalid after successful reset.
        All existing sessions are revoked.
        Does NOT affect TOTP enrollment or account active status.

        Args:
            token: JWT reset token string.
            new_password: New password to set.

        Returns:
            PasswordResetResult with success status.

        Raises:
            InvalidTokenError: Token is invalid or has been used.
            TokenExpiredError: Token has expired.
            UserNotFoundError: User no longer exists.
        """
        try:
            payload = self._jwt.verify_reset_token(token)
        except TokenExpiredError:
            raise TokenExpiredError(
                "Password reset link has expired",
                hint="Request a new password reset email",
            ) from None
        except InvalidTokenError:
            raise InvalidTokenError(
                "Invalid password reset link",
                hint="Check the link or request a new password reset",
            ) from None

        user_id = uuid.UUID(payload.sub)
        user = await self._user_repo.get(user_id)
        if user is None or user.deleted_at is not None:
            raise UserNotFoundError("User not found")

        new_hash = self._password_manager.hash_password(new_password)
        await self._user_repo.update(user_id, password_hash=new_hash)

        await self._token_repo.revoke_user_tokens(user_id)

        return PasswordResetResult(success=True)
