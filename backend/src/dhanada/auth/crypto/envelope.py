"""Envelope encryption with key rotation support.

Architecture:
    - KEK (Key Encryption Key): 32-byte key from env (base64-encoded)
    - DEK (Data Encryption Key): Random 32-byte key per secret
    - Encryption: AES-256-GCM (nonce: 12 bytes, tag: 16 bytes)
    - Key wrapping: AES-256-GCM wrapping of DEK with KEK
    - Key rotation: Each payload stores the key_id used to wrap the DEK

Flow:
    encrypt(plaintext):
        1. Generate random DEK (32 bytes)
        2. Encrypt plaintext with DEK using AES-256-GCM
        3. Encrypt DEK with current KEK using AES-256-GCM (key wrapping)
        4. Return EncryptedPayload(ciphertext+tag, nonce, encrypted_dek, key_id)

    decrypt(payload):
        1. Look up KEK by payload.key_id
        2. Decrypt DEK with KEK
        3. Decrypt ciphertext with DEK
        4. Return plaintext
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

    key_id: str = "kek_0"
    """ID of the KEK used to wrap the DEK (for key rotation)."""

    @classmethod
    def from_components(
        cls, ciphertext: bytes, nonce: bytes, encrypted_dek: bytes, key_id: str = "kek_0"
    ) -> "EncryptedPayload":
        """Reconstruct an EncryptedPayload from stored components."""
        return cls(
            ciphertext=ciphertext,
            nonce=nonce,
            encrypted_dek=encrypted_dek,
            key_id=key_id,
        )


class EnvelopeEncryption:
    """Envelope encryption for TOTP secrets using AES-256-GCM."""

    def __init__(self, kek_manager: KEKManager) -> None:
        self._kek_manager = kek_manager

    def encrypt(self, plaintext: bytes) -> EncryptedPayload:
        """Encrypt data using envelope encryption.

        Args:
            plaintext: Data to encrypt (TOTP secret bytes).

        Returns:
            EncryptedPayload containing all data needed for decryption.
        """
        dek = os.urandom(DEK_SIZE)

        nonce = os.urandom(AES_GCM_NONCE_SIZE)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        kek = self._kek_manager.current_key
        dek_nonce = os.urandom(AES_GCM_NONCE_SIZE)
        kek_aesgcm = AESGCM(kek)
        encrypted_dek = kek_aesgcm.encrypt(dek_nonce, dek, None)

        wrapped_dek = dek_nonce + encrypted_dek

        return EncryptedPayload(
            ciphertext=ciphertext,
            nonce=nonce,
            encrypted_dek=wrapped_dek,
            key_id=self._kek_manager.current_key_id,
        )

    def decrypt(self, payload: EncryptedPayload) -> bytes:
        """Decrypt data using envelope encryption.

        Args:
            payload: EncryptedPayload from a previous encrypt() call.

        Returns:
            Decrypted plaintext bytes.
        """
        try:
            kek = self._kek_manager.get_key(payload.key_id)

            dek_nonce = payload.encrypted_dek[:AES_GCM_NONCE_SIZE]
            dek_ciphertext = payload.encrypted_dek[AES_GCM_NONCE_SIZE:]

            kek_aesgcm = AESGCM(kek)
            dek = kek_aesgcm.decrypt(dek_nonce, dek_ciphertext, None)

            aesgcm = AESGCM(dek)
            plaintext = aesgcm.decrypt(payload.nonce, payload.ciphertext, None)

            return plaintext

        except Exception as e:
            raise EncryptionError(
                "Failed to decrypt data",
                hint="The KEK may have changed or the data may be corrupted",
            ) from e
