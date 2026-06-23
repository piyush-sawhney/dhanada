"""Add password_reset_version column for single-use reset tokens.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_reset_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "password_reset_version", schema="auth")
