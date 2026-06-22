"""Tests for envelope encryption."""

import os

import pytest

from dhanada.auth.crypto.envelope import EncryptedPayload, EnvelopeEncryption
from dhanada.auth.crypto.keys import KEKManager
from dhanada.auth.exceptions import ConfigurationError, EncryptionError


class TestKEKManager:
    def test_generate_returns_32_bytes(self):
        """Generated KEK should be exactly 32 bytes."""
        mgr, b64 = KEKManager.generate()
        assert len(mgr.kek) == 32
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_from_env_valid(self):
        """Loading KEK from valid base64 should succeed."""
        _, b64 = KEKManager.generate()
        mgr = KEKManager.from_env(b64)
        assert len(mgr.kek) == 32

    def test_from_env_invalid_not_base64(self):
        """Loading KEK from invalid base64 should raise."""
        with pytest.raises(ConfigurationError):
            KEKManager.from_env("not-valid-base64!!")

    def test_from_env_wrong_length(self):
        """Loading KEK with wrong decoded length should raise."""
        import base64

        short = base64.b64encode(os.urandom(16)).decode()
        with pytest.raises(ConfigurationError):
            KEKManager.from_env(short)


class TestEnvelopeEncryption:
    def test_encrypt_decrypt_roundtrip(self, envelope_encryption):
        """Encrypting then decrypting should return original data."""
        original = b"this-is-a-totp-secret-JBSWY3DPEHPK3PXP"
        encrypted = envelope_encryption.encrypt(original)
        decrypted = envelope_encryption.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_returns_payload_with_all_fields(self, envelope_encryption):
        """Encrypted payload should contain all required fields."""
        result = envelope_encryption.encrypt(b"test-secret")
        assert isinstance(result, EncryptedPayload)
        assert len(result.ciphertext) > 0
        assert len(result.nonce) == 12
        assert len(result.encrypted_dek) == 12 + 48  # nonce(12) + encrypted_dek(48)

    def test_encrypt_different_each_time(self, envelope_encryption):
        """Each encryption should produce different output (randomized)."""
        data = b"same-data"
        r1 = envelope_encryption.encrypt(data)
        r2 = envelope_encryption.encrypt(data)
        assert r1.ciphertext != r2.ciphertext
        assert r1.nonce != r2.nonce
        assert r1.encrypted_dek != r2.encrypted_dek

    def test_decrypt_wrong_key_fails(self, envelope_encryption):
        """Decrypting with different KEK should fail."""
        data = b"test-data"
        encrypted = envelope_encryption.encrypt(data)
        other_kek, _ = KEKManager.generate()
        other = EnvelopeEncryption(other_kek)
        with pytest.raises(EncryptionError):
            other.decrypt(encrypted)

    def test_decrypt_tampered_ciphertext_fails(self, envelope_encryption):
        """Decrypting corrupted ciphertext should raise."""
        data = b"test-data"
        encrypted = envelope_encryption.encrypt(data)
        corrupted = EncryptedPayload(
            ciphertext=b"\x00" + encrypted.ciphertext[1:],
            nonce=encrypted.nonce,
            encrypted_dek=encrypted.encrypted_dek,
        )
        with pytest.raises(EncryptionError):
            envelope_encryption.decrypt(corrupted)

    def test_from_components_reconstruct(self):
        """EncryptedPayload.from_components should reconstruct correctly."""
        enc = EncryptedPayload(
            ciphertext=b"ct",
            nonce=b"nonce1234567",
            encrypted_dek=b"dek12345",
        )
        recon = EncryptedPayload.from_components(
            ciphertext=b"ct",
            nonce=b"nonce1234567",
            encrypted_dek=b"dek12345",
        )
        assert enc == recon

    def test_encrypt_empty_bytes_allowed(self, envelope_encryption):
        """Encrypting empty bytes should work."""
        result = envelope_encryption.encrypt(b"")
        decrypted = envelope_encryption.decrypt(result)
        assert decrypted == b""
