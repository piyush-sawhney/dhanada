#!/usr/bin/env python3
"""Generate a base64-encoded 32-byte Key Encryption Key (KEK).

Usage:
    python scripts/generate_kek.py

Output:
    A base64-encoded 32-byte KEK suitable for DHANADA_AUTH_KEK_BASE64.
"""

import base64
import os


def generate_kek() -> tuple[bytes, str]:
    """Generate a random 32-byte KEK.

    Returns:
        Tuple of (raw KEK bytes, base64-encoded string).
    """
    kek = os.urandom(32)
    kek_b64 = base64.b64encode(kek).decode()
    return kek, kek_b64


def main() -> None:
    """Print a new KEK to stdout."""
    _, kek_b64 = generate_kek()
    print("=" * 70)
    print("  Key Encryption Key (KEK) Generated")
    print("=" * 70)
    print()
    print("  Add this to your .env file:")
    print()
    print(f"  DHANADA_AUTH_KEK_BASE64={kek_b64}")
    print()
    print("  WARNING: Store this key securely. If lost,")
    print("  all encrypted TOTP secrets will be inaccessible.")
    print("=" * 70)


if __name__ == "__main__":
    main()
