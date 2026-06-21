"""Tests for password hashing."""

import pytest

from dhanada.auth.auth.passwords import PasswordManager


class TestPasswordManager:
    def test_hash_password_returns_string(self, password_manager):
        """Hashed password should be a non-empty string."""
        hashed = password_manager.hash_password("SecurePass123!")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_uses_argon2id(self, password_manager):
        """Hash should start with argon2id scheme marker."""
        hashed = password_manager.hash_password("SecurePass123!")
        assert hashed.startswith("$argon2id$")

    def test_verify_correct_password(self, password_manager):
        """Correct password should verify against its hash."""
        password = "SecurePass123!"
        hashed = password_manager.hash_password(password)
        assert password_manager.verify_password(password, hashed) is True

    def test_verify_incorrect_password(self, password_manager):
        """Incorrect password should fail verification."""
        hashed = password_manager.hash_password("SecurePass123!")
        assert password_manager.verify_password("WrongPassword!", hashed) is False

    def test_verify_empty_password(self, password_manager):
        """Empty password should fail against any hash."""
        hashed = password_manager.hash_password("SecurePass123!")
        assert password_manager.verify_password("", hashed) is False

    def test_different_passwords_different_hashes(self, password_manager):
        """Different passwords should produce different hashes."""
        h1 = password_manager.hash_password("Password1!")
        h2 = password_manager.hash_password("Password2!")
        assert h1 != h2

    def test_same_password_different_hashes(self, password_manager):
        """Same password should produce different hashes (salting)."""
        h1 = password_manager.hash_password("SamePass123!")
        h2 = password_manager.hash_password("SamePass123!")
        assert h1 != h2

    def test_needs_upgrade_new_hash(self, password_manager):
        """Fresh hash with current algorithm should not need upgrade."""
        hashed = password_manager.hash_password("SecurePass123!")
        assert password_manager.needs_upgrade(hashed) is False

    def test_hash_long_password(self, password_manager):
        """Very long passwords should be handled."""
        long_password = "a" * 1000
        hashed = password_manager.hash_password(long_password)
        assert password_manager.verify_password(long_password, hashed) is True

    def test_hash_special_characters(self, password_manager):
        """Passwords with special characters should work."""
        special = "P@ssw0rd!~#$%^&*()_+-=[]{}|;':\",./<>?"
        hashed = password_manager.hash_password(special)
        assert password_manager.verify_password(special, hashed) is True

    def test_hash_unicode_password(self, password_manager):
        """Unicode passwords should be handled."""
        unicode_pass = "Pässwörd_123_日本語"
        hashed = password_manager.hash_password(unicode_pass)
        assert password_manager.verify_password(unicode_pass, hashed) is True

    def test_unicode_mismatch(self, password_manager):
        """Unicode-normalization differences should be handled."""
        password = "café"
        # Some users might NFC, some NFD - this test is just documenting behavior
        hashed = password_manager.hash_password(password)
        # NFC form
        import unicodedata
        assert password_manager.verify_password(
            unicodedata.normalize("NFC", password), hashed
        )