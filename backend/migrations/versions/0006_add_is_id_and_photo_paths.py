"""Add is_id, front_photo_path, back_photo_path columns for dual storage.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add is_id discriminator — existing rows are IDs (backward compatible)
    op.add_column(
        "documents",
        sa.Column("is_id", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="crm",
    )

    # Add filesystem path columns (nullable, only used when is_id=false)
    op.add_column(
        "documents",
        sa.Column("front_photo_path", sa.String(500), nullable=True),
        schema="crm",
    )
    op.add_column(
        "documents",
        sa.Column("back_photo_path", sa.String(500), nullable=True),
        schema="crm",
    )


def downgrade() -> None:
    op.drop_column("documents", "back_photo_path", schema="crm")
    op.drop_column("documents", "front_photo_path", schema="crm")
    op.drop_column("documents", "is_id", schema="crm")
