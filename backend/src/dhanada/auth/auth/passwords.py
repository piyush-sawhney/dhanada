"""Password hashing with Argon2id."""

from passlib.context import CryptContext

from dhanada.auth.constants import DEFAULT_BCRYPT_ROUNDS


class PasswordManager:
    """Password hashing and verification using Argon2id.

    Uses passlib with Argon2id as the primary algorithm and bcrypt
    as a fallback for verifying legacy hashes.
    """

    def __init__(self, bcrypt_rounds: int = DEFAULT_BCRYPT_ROUNDS) -> None:
        self._context = CryptContext(
            schemes=["argon2id", "bcrypt"],
            default="argon2id",
            argon2id__type="id",
            argon2id__time_cost=3,
            argon2id__memory_cost=65536,  # 64 MB
            argon2id__parallelism=4,
            argon2id__salt_size=16,
            bcrypt__rounds=bcrypt_rounds,
        )

    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2id.

        Args:
            password: Plain-text password.

        Returns:
            Hashed password string.
        """
        return self._context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain-text password to verify.
            password_hash: Stored password hash.

        Returns:
            True if password matches the hash.
        """
        return self._context.verify(password, password_hash)

    def needs_upgrade(self, password_hash: str) -> bool:
        """Check if a password hash needs upgrade to newer algorithm.

        Args:
            password_hash: Stored password hash.

        Returns:
            True if the hash should be re-hashed with current defaults.
        """
        return self._context.needs_update(password_hash)
