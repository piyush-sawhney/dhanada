"""TOTPSecret model with encrypted TOTP secrets."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import BaseModel

if TYPE_CHECKING:
    from dhanada.auth.models.user import User


class TOTPSecret(BaseModel):
    """TOTP secret encrypted at rest using envelope encryption.

    The actual TOTP secret is encrypted with AES-256-GCM using a
    per-secret Data Encryption Key (DEK), which is itself encrypted
    with a Key Encryption Key (KEK) stored in environment variables.
    """

    __tablename__ = "totp_secrets"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Envelope encryption fields
    encrypted_secret: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM encrypted TOTP secret (ciphertext + tag)",
    )
    encrypted_nonce: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Nonce used for AES-256-GCM encryption",
    )
    encrypted_dek: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Data Encryption Key encrypted with KEK",
    )
    encryption_key_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="kek_0",
        server_default="kek_0",
        comment="KEK ID used to wrap the DEK (for key rotation)",
    )

    # TOTP configuration
    algorithm: Mapped[str] = mapped_column(
        String(10),
        default="SHA1",
        nullable=False,
    )
    digits: Mapped[int] = mapped_column(
        Integer,
        default=6,
        nullable=False,
        comment="Number of digits in TOTP code",
    )
    period: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="TOTP validity period in seconds",
    )

    # Verification state
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Backup codes (bcrypt hashed)
    backup_codes: Mapped[list[str] | None] = mapped_column(
        JSON,
        default=list,
        nullable=True,
        comment="List of bcrypt-hashed backup codes",
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="totp_secret",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TOTPSecret(user_id={self.user_id}, verified={self.is_verified})>"
