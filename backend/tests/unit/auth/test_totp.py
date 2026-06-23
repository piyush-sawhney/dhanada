"""Tests for TOTP generation and validation."""

import pyotp

from dhanada.auth.crypto.envelope import EncryptedPayload


class TestTOTPManager:
    def test_generate_secret_returns_base32(self, totp_manager):
        """Generated secret should be valid base32."""
        secret = totp_manager.generate_secret()
        # base32 strings are uppercase A-Z and 2-7
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in secret.upper())

    def test_generate_secret_length(self, totp_manager):
        """Generated secret should be at least 16 chars (appropriate entropy)."""
        secret = totp_manager.generate_secret()
        assert len(secret) >= 16

    def test_get_provisioning_uri_format(self, totp_manager):
        """Provisioning URI should start with otpauth://totp/."""
        secret = totp_manager.generate_secret()
        uri = totp_manager.get_provisioning_uri(secret, "test@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "test%40example.com" in uri
        assert "Dhanada Test" in uri or "Dhanada" in uri

    def test_verify_valid_token(self, totp_manager):
        """Valid TOTP token should verify."""
        secret = totp_manager.generate_secret()
        totp = pyotp.TOTP(secret)
        token = totp.now()
        assert totp_manager.verify(secret, token) is True

    def test_verify_invalid_token(self, totp_manager):
        """Invalid TOTP token should fail verification."""
        secret = totp_manager.generate_secret()
        assert totp_manager.verify(secret, "000000") is False

    def test_verify_wrong_secret(self, totp_manager):
        """Token from one secret should not verify against another."""
        secret1 = totp_manager.generate_secret()
        secret2 = totp_manager.generate_secret()
        totp1 = pyotp.TOTP(secret1)
        token = totp1.now()
        assert totp_manager.verify(secret2, token) is False

    def test_encrypt_decrypt_secret_roundtrip(self, totp_manager):
        """Encrypting then decrypting should return original secret."""
        secret = totp_manager.generate_secret()
        encrypted = totp_manager.encrypt_secret(secret)
        decrypted = totp_manager.decrypt_secret(encrypted)
        assert decrypted == secret

    def test_encrypt_produces_different_output(self, totp_manager):
        """Each encryption of same secret should differ (randomized nonce)."""
        secret = totp_manager.generate_secret()
        e1 = totp_manager.encrypt_secret(secret)
        e2 = totp_manager.encrypt_secret(secret)
        assert e1.ciphertext != e2.ciphertext
        assert e1.nonce != e2.nonce

    def test_enroll_returns_all_fields(self, totp_manager):
        """Enrollment should return secret, URI, and encrypted data."""
        secret = totp_manager.generate_secret()
        result = totp_manager.enroll(secret, "user@example.com")
        assert result.secret == secret
        assert result.provisioning_uri.startswith("otpauth://totp/")
        assert isinstance(result.encrypted_secret, EncryptedPayload)

    def test_verify_with_window(self, totp_manager):
        """Token should verify within configured window."""
        secret = totp_manager.generate_secret()
        totp = pyotp.TOTP(secret)
        # The window of 1 means ±30 seconds, so the previous token works
        assert totp_manager.verify(secret, totp.now()) is True

    def test_generate_backup_codes_count(self, totp_manager):
        """Should generate exactly BACKUP_CODE_COUNT backup codes."""
        codes = totp_manager.generate_backup_codes()
        from dhanada.auth.constants import BACKUP_CODE_COUNT

        assert len(codes) == BACKUP_CODE_COUNT

    def test_generate_backup_codes_unique(self, totp_manager):
        """Each generated backup code should be unique."""
        codes = totp_manager.generate_backup_codes()
        assert len(set(codes)) == len(codes)

    def test_decrypt_and_verify_roundtrip(self, totp_manager):
        """Decrypting then verifying should work end-to-end."""
        secret = totp_manager.generate_secret()
        encrypted = totp_manager.encrypt_secret(secret)
        decrypted = totp_manager.decrypt_secret(encrypted)
        totp = pyotp.TOTP(decrypted)
        assert totp_manager.verify(decrypted, totp.now()) is True
