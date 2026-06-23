"""Key management for envelope encryption with rotation support."""

import base64
import os
from dataclasses import dataclass, field

from dhanada.auth.constants import KEK_SIZE
from dhanada.auth.exceptions import ConfigurationError


@dataclass
class KEKManager:
    """Manages Key Encryption Keys (KEKs) for envelope encryption.

    Supports key rotation via multiple KEK IDs.
    Previous keys (oldest first) get IDs ``kek_0``, ``kek_1``, ...
    The current key always gets the highest ID.
    """

    _keys: dict[str, bytes] = field(default_factory=dict, repr=False)
    _current_key_id: str = field(default="kek_0")

    @classmethod
    def from_env(
        cls,
        kek_base64: str,
        previous_base64_keys: list[str] | None = None,
    ) -> "KEKManager":
        """Load KEKs from environment values.

        Args:
            kek_base64: Current base64-encoded 32-byte KEK.
            previous_base64_keys: Previous KEKs (oldest first) for decryption.

        Returns:
            KEKManager with auto-assigned key IDs.
        """
        keys: dict[str, bytes] = {}
        previous = previous_base64_keys or []

        for i, encoded in enumerate(previous):
            key_id = f"kek_{i}"
            keys[key_id] = _decode_kek(encoded)

        current_id = f"kek_{len(previous)}"
        keys[current_id] = _decode_kek(kek_base64)

        return cls(_keys=keys, _current_key_id=current_id)

    @property
    def current_key(self) -> bytes:
        """Return the current KEK bytes."""
        return self._keys[self._current_key_id]

    @property
    def current_key_id(self) -> str:
        """Return the current KEK ID."""
        return self._current_key_id

    def get_key(self, key_id: str) -> bytes:
        """Look up a KEK by ID.

        Raises:
            ConfigurationError: Key ID not found.
        """
        try:
            return self._keys[key_id]
        except KeyError:
            raise ConfigurationError(
                f"KEK '{key_id}' not found",
                hint="Check that the corresponding key was provided in kek_previous_base64_keys",
            ) from None

    @classmethod
    def generate(cls) -> tuple["KEKManager", str]:
        """Generate a new random KEK.

        Returns:
            Tuple of (KEKManager instance, base64-encoded key string).
        """
        kek = os.urandom(KEK_SIZE)
        kek_b64 = base64.b64encode(kek).decode()
        return cls(_keys={"kek_0": kek}, _current_key_id="kek_0"), kek_b64


def _decode_kek(encoded: str) -> bytes:
    """Decode and validate a base64-encoded KEK."""
    try:
        kek = base64.b64decode(encoded)
    except Exception as e:
        raise ConfigurationError(
            "Invalid KEK: must be valid base64",
            hint=(
                "Generate with: python -c 'import base64, os; "
                "print(base64.b64encode(os.urandom(32)).decode())'"
            ),
        ) from e

    if len(kek) != KEK_SIZE:
        raise ConfigurationError(
            f"KEK must be {KEK_SIZE} bytes, got {len(kek)}",
            hint=f"Generate a {KEK_SIZE}-byte key encoded in base64",
        )

    return kek
