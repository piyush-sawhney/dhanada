"""Add failed_login_attempts and locked_until to users.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
