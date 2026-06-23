"""Email verification service."""

import uuid
from dataclasses import dataclass

from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.db.repository import UserRepository
from dhanada.auth.email.sender import EmailSender
from dhanada.auth.exceptions import InvalidTokenError, TokenExpiredError, UserNotFoundError


@dataclass
class VerificationResult:
    """Result of email verification."""

    verified: bool
    email: str | None = None


class VerificationService:
    """Email verification token generation and confirmation."""

    def __init__(
        self,
        jwt_manager: JWTManager,
        user_repo: UserRepository,
        base_url: str,
        token_ttl_minutes: int,
        email_sender: EmailSender | None = None,
    ) -> None:
        self._jwt = jwt_manager
        self._user_repo = user_repo
        self._email_sender = email_sender
        self._base_url = base_url
        self._token_ttl = token_ttl_minutes

    async def send_verification(self, user_id: uuid.UUID) -> bool:
        """Generate and send a verification email to the user.

        Args:
            user_id: User UUID.

        Returns:
            True if the email was sent successfully.
        """
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        if user.email_verified:
            return True

        token = self._jwt.create_verification_token(user_id, self._token_ttl)
        verification_url = f"{self._base_url}/api/auth/verify-email?token={token}"

        if self._email_sender is None:
            return False

        return await self._email_sender.send_verification_email(
            to=user.email,
            username=user.username,
            verification_url=verification_url,
        )

    async def verify(self, token: str) -> VerificationResult:
        """Verify an email verification token.

        Args:
            token: JWT verification token string.

        Returns:
            VerificationResult with status and email.

        Raises:
            InvalidTokenError: Token is invalid.
            TokenExpiredError: Token has expired.
        """
        try:
            payload = self._jwt.verify_verification_token(token)
        except TokenExpiredError:
            raise TokenExpiredError(
                "Verification link has expired",
                hint="Request a new verification email",
            ) from None
        except InvalidTokenError:
            raise InvalidTokenError(
                "Invalid verification link",
                hint="Check the link or request a new verification email",
            ) from None

        user_id = uuid.UUID(payload.sub)
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError("User not found")

        if user.email_verified:
            return VerificationResult(verified=True, email=user.email)

        await self._user_repo.update(user_id, email_verified=True)
        return VerificationResult(verified=True, email=user.email)
