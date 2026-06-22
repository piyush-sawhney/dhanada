"""Initial schema with audit columns, soft-delete, and UserRole model.

Revision ID: 0001
Revises: None
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create auth schema
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, index=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_superuser", sa.Boolean(), default=False, nullable=False),
        sa.Column("email_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        schema="auth",
    )

    # --- roles ---
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        schema="auth",
    )

    # --- role_permissions ---
    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.roles.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("resource", sa.String(100), index=True, nullable=False),
        sa.Column("action", sa.String(50), index=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("role_id", "resource", "action", name="uq_role_resource_action"),
        schema="auth",
    )

    # --- user_roles (association model) ---
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        schema="auth",
    )

    # --- totp_secrets ---
    op.create_table(
        "totp_secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False),
        sa.Column("encrypted_secret", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=False),
        sa.Column("algorithm", sa.String(10), default="SHA1", nullable=False),
        sa.Column("digits", sa.Integer(), default=6, nullable=False),
        sa.Column("period", sa.Integer(), default=30, nullable=False),
        sa.Column("is_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backup_codes", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        schema="auth",
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("token_hash", sa.String(128), index=True, nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), index=True, nullable=False),
        sa.Column("parent_token_hash", sa.String(128), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), index=True, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        schema="auth",
    )

    # --- crm schema ---
    op.execute("CREATE SCHEMA IF NOT EXISTS crm")

    # --- clients ---
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), index=True, nullable=False),
        sa.Column("pan_number_hash", sa.String(128), unique=True, index=True, nullable=False),
        sa.Column("encrypted_pan", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="crm",
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm.clients.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("document_number", sa.String(100), index=True, nullable=True),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("document_type_other", sa.String(255), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("front_photo_data", sa.LargeBinary(), nullable=True),
        sa.Column("front_photo_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("front_photo_dek", sa.LargeBinary(), nullable=True),
        sa.Column("front_photo_mime", sa.String(50), nullable=True),
        sa.Column("back_photo_data", sa.LargeBinary(), nullable=True),
        sa.Column("back_photo_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("back_photo_dek", sa.LargeBinary(), nullable=True),
        sa.Column("back_photo_mime", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="crm",
    )

    # Partial unique index on document_number
    op.create_index(
        "uq_document_number",
        "documents",
        ["document_number"],
        unique=True,
        postgresql_where=sa.text("document_number IS NOT NULL"),
        schema="crm",
    )


def downgrade() -> None:
    op.drop_table("documents", schema="crm")
    op.drop_table("clients", schema="crm")
    op.drop_table("refresh_tokens", schema="auth")
    op.drop_table("totp_secrets", schema="auth")
    op.drop_table("user_roles", schema="auth")
    op.drop_table("role_permissions", schema="auth")
    op.drop_table("roles", schema="auth")
    op.drop_table("users", schema="auth")
