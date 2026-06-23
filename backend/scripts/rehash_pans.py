#!/usr/bin/env python3
# ruff: noqa: T201
"""One-time data migration: rehash PAN hashes from SHA-256 to HMAC-SHA256.

Previously, PAN numbers were hashed with plain SHA-256 (unsalted).
This script computes the new HMAC-SHA256 hash for each existing client
and updates the pan_number_hash column in-place.

Usage:
    python scripts/rehash_pans.py [--dry-run]

Requires the same .env configuration as the main application.
Idempotent: running multiple times produces the same result.

Note: runs synchronously for simplicity (one-time migration).
"""

import argparse
import base64
import hmac
import os

import sqlalchemy as sa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decrypt_pan(
    encrypted_pan: bytes,
    encrypted_nonce: bytes,
    encrypted_dek: bytes,
    kek: bytes,
) -> str:
    """Decrypt a PAN using the same envelope encryption as the application."""
    aes_gcm_nonce_size = 12
    dek_nonce = encrypted_dek[:aes_gcm_nonce_size]
    dek_ciphertext = encrypted_dek[aes_gcm_nonce_size:]

    kek_aesgcm = AESGCM(kek)
    dek = kek_aesgcm.decrypt(dek_nonce, dek_ciphertext, None)

    aesgcm = AESGCM(dek)
    plaintext = aesgcm.decrypt(encrypted_nonce, encrypted_pan, None)
    return plaintext.decode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rehash PAN hashes to HMAC-SHA256")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    database_url = os.environ["DHANADA_DATABASE_URL"]
    kek_b64 = os.environ["DHANADA_AUTH_KEK_BASE64"]
    pan_hmac_key = os.environ["DHANADA_AUTH_PAN_HMAC_KEY"].encode()

    kek = base64.b64decode(kek_b64)

    print("=" * 60)
    print("  PAN Hash Re-migration")
    print("=" * 60)
    print(f"  Database: {database_url}")
    print(f"  Dry run:  {args.dry_run}")
    print()

    sync_url = database_url.replace("+asyncpg", "")
    engine = sa.create_engine(sync_url)

    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                """
                SELECT id, encrypted_pan, encrypted_nonce, encrypted_dek
                FROM crm.clients
                WHERE encrypted_pan IS NOT NULL
                """
            )
        ).fetchall()

        print(f"  Found {len(rows)} client(s) with PAN data.")
        print()

        count = 0
        for row in rows:
            client_id = row[0]
            encrypted_pan = bytes(row[1])
            encrypted_nonce = bytes(row[2])
            encrypted_dek = bytes(row[3])

            pan = decrypt_pan(encrypted_pan, encrypted_nonce, encrypted_dek, kek)
            pan_normalized = pan.replace(" ", "").upper()
            new_hash = hmac.new(pan_hmac_key, pan_normalized.encode(), "sha256").hexdigest()

            if args.dry_run:
                print(f"  Would update client {client_id}: hash={new_hash[:16]}...")
                count += 1
                continue

            conn.execute(
                sa.text("UPDATE crm.clients SET pan_number_hash = :hash WHERE id = :id"),
                {"hash": new_hash, "id": client_id},
            )
            count += 1

            if count % 100 == 0:
                print(f"  Progress: {count} clients updated...")
                conn.commit()

        if not args.dry_run:
            conn.commit()

    print()
    if args.dry_run:
        print(f"  Would update {count} client(s). Run without --dry-run to apply.")
    else:
        print(f"  Updated {count} client(s).")
    print("=" * 60)


if __name__ == "__main__":
    main()
