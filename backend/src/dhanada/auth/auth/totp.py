"""TOTP generation and validation."""

import secrets
from dataclasses import dataclass

import pyotp

from dhanada.auth.constants import BACKUP_CODE_COUNT, BACKUP_CODE_LENGTH
from dhanada.auth.crypto.envelope import EncryptedPayload, EnvelopeEncryption


@dataclass
class TOTPEnrollment:
    """Result of a TOTP enrollment request."""

    secret: str
    """Plain-text TOTP secret (shown once for QR code scan)."""

    provisioning_uri: str
    """URI for QR code generation (otpauth://totp/...)."""

    encrypted_secret: EncryptedPayload
    """Encrypted TOTP secret for database storage."""


class TOTPManager:
    """TOTP (Time-based One-Time Password) generation and validation.

    Uses pyotp for TOTP operations and envelope encryption for
    secure storage of TOTP secrets.
    """

    def __init__(
        self,
        encryption: EnvelopeEncryption,
        issuer: str = "Dhanada",
        window: int = 1,
    ) -> None:
        self._encryption = encryption
        self._issuer = issuer
        self._window = window

    def generate_secret(self) -> str:
        """Generate a new random TOTP secret in base32.

        Returns:
            Base32-encoded TOTP secret string.
        """
        return pyotp.random_base32()

    def get_provisioning_uri(self, secret: str, email: str) -> str:
        """Generate a provisioning URI for QR codes.

        Args:
            secret: Base32 TOTP secret.
            email: User email for identification in authenticator app.

        Returns:
            otpauth:// URI for QR code generation.
        """
        totp = pyotp.TOTP(secret, issuer=self._issuer)
        return totp.provisioning_uri(name=email, issuer_name=self._issuer)

    def verify(self, secret: str, token: str) -> bool:
        """Verify a TOTP token.

        Args:
            secret: Base32 TOTP secret.
            token: 6-digit TOTP code from authenticator app.

        Returns:
            True if token is valid within the configured time window.
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=self._window)

    def encrypt_secret(self, secret: str) -> EncryptedPayload:
        """Encrypt a TOTP secret for database storage.

        Args:
            secret: Plain-text base32 TOTP secret.

        Returns:
            EncryptedPayload for storage in TOTPSecret model.
        """
        return self._encryption.encrypt(secret.encode())

    def decrypt_secret(self, payload: EncryptedPayload) -> str:
        """Decrypt a TOTP secret for verification.

        Args:
            payload: EncryptedPayload from database.

        Returns:
            Plain-text base32 TOTP secret.
        """
        return self._encryption.decrypt(payload).decode()

    def enroll(self, secret: str, email: str) -> TOTPEnrollment:
        """Create a full enrollment package for a new TOTP setup.

        Args:
            secret: Plain-text base32 TOTP secret.
            email: User email for provisioning URI.

        Returns:
            TOTPEnrollment with plain-text secret, URI, and encrypted data.
        """
        provisioning_uri = self.get_provisioning_uri(secret, email)
        encrypted = self.encrypt_secret(secret)
        return TOTPEnrollment(
            secret=secret,
            provisioning_uri=provisioning_uri,
            encrypted_secret=encrypted,
        )

    def generate_backup_codes(self) -> list[str]:
        """Generate backup recovery codes.

        Returns:
            List of BACKUP_CODE_COUNT plain-text backup codes.
        """
        codes: list[str] = []
        for _ in range(BACKUP_CODE_COUNT):
            code = secrets.token_urlsafe(BACKUP_CODE_LENGTH)[:BACKUP_CODE_LENGTH]
            codes.append(code)
        return codes
