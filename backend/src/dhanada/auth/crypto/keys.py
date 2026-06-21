"""Key management for envelope encryption."""

import base64
import os
from dataclasses import dataclass

from dhanada.auth.constants import KEK_SIZE
from dhanada.auth.exceptions import ConfigurationError


@dataclass
class KEKManager:
    """Manages the Key Encryption Key (KEK) for envelope encryption.

    The KEK is loaded from an environment variable as a base64-encoded
    32-byte key. This is suitable for development and small deployments.
    For production, consider using AWS KMS, GCP KMS, or HashiCorp Vault.
    """

    kek: bytes

    @classmethod
    def from_env(cls, kek_base64: str) -> "KEKManager":
        """Load KEK from a base64-encoded environment variable value."""
        try:
            kek = base64.b64decode(kek_base64)
        except Exception as e:
            raise ConfigurationError(
                "Invalid KEK: must be valid base64",
                hint="Generate with: python -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())'",
            ) from e

        if len(kek) != KEK_SIZE:
            raise ConfigurationError(
                f"KEK must be {KEK_SIZE} bytes, got {len(kek)}",
                hint=f"Generate a {KEK_SIZE}-byte key encoded in base64",
            )

        return cls(kek=kek)

    @classmethod
    def generate(cls) -> tuple["KEKManager", str]:
        """Generate a new random KEK.

        Returns:
            Tuple of (KEKManager instance, base64-encoded key string).
        """
        kek = os.urandom(KEK_SIZE)
        kek_b64 = base64.b64encode(kek).decode()
        return cls(kek=kek), kek_b64