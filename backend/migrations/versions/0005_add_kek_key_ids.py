"""Add key_id columns to all encrypted payloads for KEK rotation.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "totp_secrets",
        sa.Column("encryption_key_id", sa.String(50), nullable=False, server_default="kek_0"),
        schema="auth",
    )
    op.add_column(
        "clients",
        sa.Column("pan_encryption_key_id", sa.String(50), nullable=False, server_default="kek_0"),
        schema="crm",
    )
    op.add_column(
        "documents",
        sa.Column("front_photo_key_id", sa.String(50), nullable=False, server_default="kek_0"),
        schema="crm",
    )
    op.add_column(
        "documents",
        sa.Column("back_photo_key_id", sa.String(50), nullable=False, server_default="kek_0"),
        schema="crm",
    )


def downgrade() -> None:
    op.drop_column("totp_secrets", "encryption_key_id", schema="auth")
    op.drop_column("clients", "pan_encryption_key_id", schema="crm")
    op.drop_column("documents", "front_photo_key_id", schema="crm")
    op.drop_column("documents", "back_photo_key_id", schema="crm")
