"""Envelope encryption for TOTP secrets.

Architecture:
    - KEK (Key Encryption Key): 32-byte key from env (base64-encoded)
    - DEK (Data Encryption Key): Random 32-byte key per secret
    - Encryption: AES-256-GCM (nonce: 12 bytes, tag: 16 bytes)
    - Key wrapping: AES-256-GCM wrapping of DEK with KEK

Flow:
    encrypt(plaintext):
        1. Generate random DEK (32 bytes)
        2. Encrypt plaintext with DEK using AES-256-GCM
        3. Encrypt DEK with KEK using AES-256-GCM (key wrapping)
        4. Return EncryptedPayload(ciphertext+tag, nonce, encrypted_dek)

    decrypt(payload):
        1. Decrypt DEK with KEK
        2. Decrypt ciphertext with DEK
        3. Return plaintext
"""

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dhanada.auth.constants import AES_GCM_NONCE_SIZE, DEK_SIZE
from dhanada.auth.crypto.keys import KEKManager
from dhanada.auth.exceptions import EncryptionError


@dataclass
class EncryptedPayload:
    """Container for envelope-encrypted data."""

    ciphertext: bytes
    """AES-256-GCM encrypted data (ciphertext + 16-byte tag concatenated)."""

    nonce: bytes
    """12-byte nonce used for AES-256-GCM encryption."""

    encrypted_dek: bytes
    """DEK encrypted with KEK (ciphertext + 16-byte tag concatenated)."""

    @classmethod
    def from_components(
        cls, ciphertext: bytes, nonce: bytes, encrypted_dek: bytes
    ) -> "EncryptedPayload":
        """Reconstruct an EncryptedPayload from stored components."""
        return cls(
            ciphertext=ciphertext,
            nonce=nonce,
            encrypted_dek=encrypted_dek,
        )


class EnvelopeEncryption:
    """Envelope encryption for TOTP secrets using AES-256-GCM."""

    def __init__(self, kek_manager: KEKManager) -> None:
        self._kek = kek_manager.kek

    def encrypt(self, plaintext: bytes) -> EncryptedPayload:
        """Encrypt data using envelope encryption.

        Args:
            plaintext: Data to encrypt (TOTP secret bytes).

        Returns:
            EncryptedPayload containing all data needed for decryption.
        """
        # 1. Generate random DEK
        dek = os.urandom(DEK_SIZE)

        # 2. Encrypt plaintext with DEK using AES-GCM
        nonce = os.urandom(AES_GCM_NONCE_SIZE)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        # 3. Encrypt DEK with KEK using AES-GCM (key wrapping)
        dek_nonce = os.urandom(AES_GCM_NONCE_SIZE)
        kek_aesgcm = AESGCM(self._kek)
        encrypted_dek = kek_aesgcm.encrypt(dek_nonce, dek, None)

        # 4. Concatenate nonce and ciphertext for DEK wrapping
        #    Format: nonce(12) + ciphertext(48 = 32 + 16)
        wrapped_dek = dek_nonce + encrypted_dek

        return EncryptedPayload(
            ciphertext=ciphertext,
            nonce=nonce,
            encrypted_dek=wrapped_dek,
        )

    def decrypt(self, payload: EncryptedPayload) -> bytes:
        """Decrypt data using envelope encryption.

        Args:
            payload: EncryptedPayload from a previous encrypt() call.

        Returns:
            Decrypted plaintext bytes.
        """
        try:
            # 1. Decrypt DEK with KEK
            dek_nonce = payload.encrypted_dek[:AES_GCM_NONCE_SIZE]
            dek_ciphertext = payload.encrypted_dek[AES_GCM_NONCE_SIZE:]

            kek_aesgcm = AESGCM(self._kek)
            dek = kek_aesgcm.decrypt(dek_nonce, dek_ciphertext, None)

            # 2. Decrypt ciphertext with DEK
            aesgcm = AESGCM(dek)
            plaintext = aesgcm.decrypt(payload.nonce, payload.ciphertext, None)

            return plaintext

        except Exception as e:
            raise EncryptionError(
                "Failed to decrypt data",
                hint="The KEK may have changed or the data may be corrupted",
            ) from e
