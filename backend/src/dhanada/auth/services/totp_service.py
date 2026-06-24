"""TOTP two-factor authentication service."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from dhanada.auth.auth.totp import TOTPManager
from dhanada.auth.crypto.envelope import EncryptedPayload
from dhanada.auth.db.repository import TOTPRepository, UserRepository
from dhanada.auth.exceptions import (
    TOTPAlreadyEnabledError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
    UserNotFoundError,
)


@dataclass
class TOTPEnrollmentResult:
    """Result of enabling TOTP."""

    secret: str
    provisioning_uri: str
    backup_codes: list[str] | None = None


class TOTPService:
    """TOTP enrollment, verification, and management."""

    def __init__(
        self,
        totp_repo: TOTPRepository,
        user_repo: UserRepository,
        totp_manager: TOTPManager,
    ) -> None:
        self._totp_repo = totp_repo
        self._user_repo = user_repo
        self._totp_manager = totp_manager

    async def _check_backup_code(self, token: str, totp_record: object) -> bool:
        """Check if token matches any backup code and consume it."""
        if not totp_record.backup_codes:
            return False
        for i, hashed_code in enumerate(totp_record.backup_codes):
            if hashlib.sha256(token.encode()).hexdigest() == hashed_code:
                remaining = totp_record.backup_codes.copy()
                remaining.pop(i)
                await self._totp_repo.update(
                    totp_record.id,
                    backup_codes=remaining,
                )
                return True
        return False

    async def _verify_totp_code(self, token: str, totp_record: object) -> bool:
        """Verify a TOTP code against the user's stored secret."""
        secret = self._totp_manager.decrypt_secret(
            EncryptedPayload.from_components(
                ciphertext=totp_record.encrypted_secret,
                nonce=totp_record.encrypted_nonce,
                encrypted_dek=totp_record.encrypted_dek,
                key_id=totp_record.encryption_key_id,
            )
        )
        return self._totp_manager.verify(secret, token)

    async def enable(
        self,
        user_id: uuid.UUID,
        generate_backup_codes: bool = True,
    ) -> TOTPEnrollmentResult:
        """Enable TOTP for a user.

        Args:
            user_id: User UUID.
            generate_backup_codes: Whether to generate backup codes.

        Returns:
            TOTPEnrollmentResult with secret, QR URI, and optional backup codes.

        Raises:
            TOTPAlreadyEnabledError: TOTP already enabled.
        """
        user = await self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")

        existing = await self._totp_repo.get_by_user_id(user_id)
        if existing is not None and existing.is_verified:
            raise TOTPAlreadyEnabledError(
                "TOTP is already enabled",
                hint="Disable TOTP first if you want to reconfigure it",
            )

        secret = self._totp_manager.generate_secret()
        enrollment = self._totp_manager.enroll(secret, user.email)
        backup_codes = None
        hashed_backup_codes: list[str] = []
        if generate_backup_codes:
            backup_codes = self._totp_manager.generate_backup_codes()
            hashed_backup_codes = [
                hashlib.sha256(code.encode()).hexdigest() for code in backup_codes
            ]

        await self._totp_repo.upsert(
            user_id=user_id,
            encrypted_secret=enrollment.encrypted_secret.ciphertext,
            encrypted_nonce=enrollment.encrypted_secret.nonce,
            encrypted_dek=enrollment.encrypted_secret.encrypted_dek,
            encryption_key_id=enrollment.encrypted_secret.key_id,
            backup_codes=hashed_backup_codes,
            is_verified=False,
        )

        return TOTPEnrollmentResult(
            secret=enrollment.secret,
            provisioning_uri=enrollment.provisioning_uri,
            backup_codes=backup_codes,
        )

    async def verify_and_confirm(self, user_id: uuid.UUID, token: str) -> bool:
        """Verify a TOTP token and mark TOTP as verified.

        Args:
            user_id: User UUID.
            token: 6-digit TOTP code or backup code.

        Returns:
            True if verification succeeded.
        """
        totp = await self._totp_repo.get_by_user_id(user_id)
        if totp is None:
            raise TOTPNotEnabledError(
                "TOTP is not enabled",
                hint="Enable TOTP first",
            )

        if totp.is_verified:
            return True

        if await self._check_backup_code(token, totp):
            await self._totp_repo.update(totp.id, is_verified=True, verified_at=datetime.now(UTC))
            return True

        if await self._verify_totp_code(token, totp):
            await self._totp_repo.update(totp.id, is_verified=True, verified_at=datetime.now(UTC))
            return True

        raise TOTPInvalidTokenError(
            "Invalid TOTP token",
            hint="Check the current code in your authenticator app",
        )

    async def verify(self, user_id: uuid.UUID, token: str) -> bool:
        """Verify a TOTP token for authentication.

        Accepts both 6-digit TOTP codes and backup codes.
        Backup codes are consumed upon use.

        Args:
            user_id: User UUID.
            token: 6-digit TOTP code or 16-char backup code.

        Returns:
            True if token is valid.
        """
        totp = await self._totp_repo.get_by_user_id(user_id)
        if totp is None or not totp.is_verified:
            raise TOTPNotEnabledError(
                "TOTP is not enabled",
                hint="Enable TOTP in your security settings",
            )

        if await self._check_backup_code(token, totp):
            return True

        return await self._verify_totp_code(token, totp)

    async def verify_totp_only(self, user_id: uuid.UUID, token: str) -> bool:
        """Verify only a 6-digit TOTP code for login.

        Does NOT accept backup codes — they are only valid in the
        recovery flow. This prevents accidental backup code consumption
        during normal login.

        Args:
            user_id: User UUID.
            token: 6-digit TOTP code.

        Returns:
            True if token is valid.

        Raises:
            TOTPNotEnabledError: TOTP is not enabled.
            TOTPInvalidTokenError: Token is invalid.
        """
        totp = await self._totp_repo.get_by_user_id(user_id)
        if totp is None or not totp.is_verified:
            raise TOTPNotEnabledError(
                "TOTP is not enabled",
                hint="Enable TOTP in your security settings",
            )

        if len(token) == 16:
            raise TOTPInvalidTokenError(
                "Backup codes cannot be used for login. "
                "Use 'Lost authenticator?' to recover with a backup code.",
            )

        return await self._verify_totp_code(token, totp)

    async def disable(self, user_id: uuid.UUID, token: str) -> bool:
        """Disable TOTP for a user.

        Requires a valid TOTP token or backup code for confirmation.
        """
        totp = await self._totp_repo.get_by_user_id(user_id)
        if totp is None:
            raise TOTPNotEnabledError("TOTP is not enabled")

        # Verify token before disabling
        if not await self.verify(user_id, token):
            raise TOTPInvalidTokenError(
                "Invalid TOTP token",
                hint="Provide a valid code to confirm disabling TOTP",
            )

        await self._totp_repo.delete(totp.id)
        return True

    async def generate_backup_codes(self, user_id: uuid.UUID) -> list[str]:
        """Generate new backup codes, invalidating old ones."""
        totp = await self._totp_repo.get_by_user_id(user_id)
        if totp is None:
            raise TOTPNotEnabledError("TOTP is not enabled")

        backup_codes = self._totp_manager.generate_backup_codes()
        hashed_codes = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]

        await self._totp_repo.update(totp.id, backup_codes=hashed_codes)
        return backup_codes

    async def is_enabled(self, user_id: uuid.UUID) -> bool:
        """Check if TOTP is enabled for a user."""
        totp = await self._totp_repo.get_by_user_id(user_id)
        return totp is not None and totp.is_verified
