"""Password hashing with Argon2id."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, VerifyMismatchError


class PasswordManager:
    """Password hashing and verification using Argon2id.

    Uses argon2-cffi directly (password hashing competition winner).
    """

    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,  # 64 MB
            parallelism=4,
            salt_len=16,
            hash_len=32,
            type=Type.ID,
        )

    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2id."""
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError):
            return False

    def needs_upgrade(self, password_hash: str) -> bool:
        """Check if a password hash needs upgrade to newer algorithm."""
        return self._hasher.check_needs_rehash(password_hash)
