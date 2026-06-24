"""Recovery service for backup code login flow."""

import uuid
from datetime import UTC, datetime, timedelta

from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.db.repository import TOTPRepository, UserRepository
from dhanada.auth.email.sender import EmailSender
from dhanada.auth.exceptions import InvalidTokenError, TokenExpiredError
from dhanada.auth.models.user import User


class RecoveryService:
    """Handles the backup-code recovery approval flow.

    When a user logs in with a backup code, an approval email is sent.
    The user must click the link to confirm recovery, which triggers
    TOTP deletion, account deactivation, and setup token issuance.
    """

    def __init__(
        self,
        jwt_manager: JWTManager,
        user_repo: UserRepository,
        totp_repo: TOTPRepository,
        email_sender: EmailSender | None,
        base_url: str,
    ) -> None:
        self._jwt_manager = jwt_manager
        self._user_repo = user_repo
        self._totp_repo = totp_repo
        self._email_sender = email_sender
        self._base_url = base_url.rstrip("/")

    async def request_recovery(
        self,
        user: User,
    ) -> bool:
        """Send a recovery approval email to the user.

        Generates a short-lived JWT that must be clicked to approve.
        The backup code has already been consumed by the login endpoint.

        Args:
            user: The authenticated user requesting recovery.
            ip_address: Client IP for audit.

        Returns:
            True if the email was sent successfully.
        """
        token = self._jwt_manager.create_recovery_approval_token(user.id)
        approval_url = f"{self._base_url}/recovery/approve?token={token}"

        if self._email_sender is None:
            return False

        return await self._email_sender.send_recovery_approval_email(
            to=user.email,
            full_name=user.full_name,
            approval_url=approval_url,
        )

    async def approve_recovery(self, token: str) -> str:
        """Verify the recovery approval token and issue a setup token.

        On approval:
        1. Delete the TOTP secret (invalidates authenticator + backup codes)
        2. Deactivate the user (triggers setup flow on next login)
        3. Generate and return a setup token

        Args:
            token: The recovery approval JWT.

        Returns:
            A setup token string for the recovered user.

        Raises:
            InvalidTokenError: Token is invalid, expired, or wrong type.
        """
        try:
            payload = self._jwt_manager.verify_recovery_approval_token(token)
        except TokenExpiredError:
            raise InvalidTokenError(
                "Recovery approval token has expired. Please start again.",
                hint="Log in with a backup code to receive a new email.",
            ) from None

        user_id = uuid.UUID(payload.sub)

        # Delete TOTP secret (clears backup codes too)
        await self._totp_repo.delete_by_user_id(user_id)

        # Deactivate user to force setup flow
        now = datetime.now(UTC)
        await self._user_repo.update(
            user_id,
            is_active=False,
            expires_at=now + timedelta(minutes=10),
        )

        # Generate setup token for the user
        setup_token = self._jwt_manager.create_setup_token(user_id)
        return setup_token
