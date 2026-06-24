"""Add expires_at to users for inactive account auto-cleanup.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Auto-expiry for inactive accounts waiting first-time setup",
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "expires_at", schema="auth")
