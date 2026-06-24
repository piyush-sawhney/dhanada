"""Add failed_login_attempts and locked_until to users.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "locked_until", schema="auth")
    op.drop_column("users", "failed_login_attempts", schema="auth")
