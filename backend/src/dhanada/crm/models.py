"""CRM models — Client with encrypted PAN and Documents."""

import re
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanada.auth.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from dhanada.auth.models.user import User

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class DocumentType(StrEnum):
    PAN_CARD = "pan_card"
    AADHAAR = "aadhaar"
    PASSPORT = "passport"
    DRIVING_LICENSE = "driving_license"
    VOTER_ID = "voter_id"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"


class CRMBaseModel(Base, UUIDMixin, TimestampMixin):
    __abstract__ = True
    __table_args__ = {"schema": "crm"}


class Client(CRMBaseModel):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pan_number_hash: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        comment="SHA-256 hash of normalized PAN for uniqueness checks",
    )

    encrypted_pan: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM encrypted PAN (ciphertext + tag)",
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

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
    updated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by_id],
        lazy="selectin",
    )
    deleted_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[deleted_by_id],
        lazy="selectin",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="client",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name={self.name})>"


class Document(CRMBaseModel):
    __tablename__ = "documents"

    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("crm.clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client: Mapped["Client"] = relationship(
        "Client",
        foreign_keys=[client_id],
        back_populates="documents",
        lazy="selectin",
    )

    document_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    document_type_other: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    front_photo_data: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    front_photo_nonce: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    front_photo_dek: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    front_photo_mime: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    back_photo_data: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    back_photo_nonce: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    back_photo_dek: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    back_photo_mime: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
    updated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by_id],
        lazy="selectin",
    )
    deleted_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[deleted_by_id],
        lazy="selectin",
    )

    __table_args__ = (  # type: ignore[assignment]
        Index(
            "uq_document_number",
            "document_number",
            unique=True,
            postgresql_where=text("document_number IS NOT NULL"),
        ),
        {"schema": "crm"},
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, type={self.document_type})>"


def normalize_pan(pan: str) -> str:
    return pan.upper().strip()


def validate_pan(pan: str) -> bool:
    return bool(PAN_PATTERN.match(normalize_pan(pan)))
