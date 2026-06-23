"""Pydantic schemas for CRM API."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from dhanada.crm.models import Document

from dhanada.crm.pan import normalize_pan as _normalize_pan
from dhanada.crm.pan import validate_pan as _validate_pan


class ClientCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    pan: str = Field(..., min_length=10, max_length=10)

    @field_validator("pan")
    @classmethod
    def check_pan(cls, v: str) -> str:
        normalized = _normalize_pan(v)
        if not _validate_pan(normalized):
            raise ValueError("PAN must match format: AAAAA1234A (5 letters, 4 digits, 1 letter)")
        return normalized


class ClientUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class ClientPanUpdateRequest(BaseModel):
    pan: str = Field(..., min_length=10, max_length=10)

    @field_validator("pan")
    @classmethod
    def check_pan(cls, v: str) -> str:
        normalized = _normalize_pan(v)
        if not _validate_pan(normalized):
            raise ValueError("PAN must match format: AAAAA1234A (5 letters, 4 digits, 1 letter)")
        return normalized


class ClientResponse(BaseModel):
    id: UUID
    name: str
    pan_number_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientDetailResponse(ClientResponse):
    """Includes decrypted PAN — only returned with manage-pan permission."""

    pan: str | None = None


class PaginatedResponse[DataT](BaseModel):
    items: list[DataT]
    total: int
    offset: int
    limit: int


class ClientListParams(BaseModel):
    search: str | None = Field(None, max_length=255)
    status: Literal["active", "inactive", "all"] = "active"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)


class DocumentCreateRequest(BaseModel):
    client_id: UUID
    document_number: str | None = Field(None, max_length=100)
    document_type: str = Field(
        ...,
        max_length=50,
        description="Document type label (e.g. pan_card, aadhaar, passport, will, poa)",
    )
    document_type_other: str | None = Field(None, max_length=255)
    is_id: bool = Field(
        True,
        description="True=ID (DB, front+back). False=other doc (filesystem, single file)",
    )
    issue_date: date
    expiry_date: date | None = None


class DocumentResponse(BaseModel):
    id: UUID
    client_id: UUID
    document_number: str | None
    document_type: str
    document_type_other: str | None
    is_id: bool
    issue_date: date
    expiry_date: date | None
    has_front_photo: bool
    has_back_photo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_document(cls, doc: Document) -> DocumentResponse:
        if doc.is_id:
            has_front = doc.front_photo_data is not None
            has_back = doc.back_photo_data is not None
        else:
            has_front = False
            has_back = False

        return cls(
            id=doc.id,
            client_id=doc.client_id,
            document_number=doc.document_number,
            document_type=doc.document_type,
            document_type_other=doc.document_type_other,
            is_id=doc.is_id,
            issue_date=doc.issue_date,
            expiry_date=doc.expiry_date,
            has_front_photo=has_front,
            has_back_photo=has_back,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class DocumentUpdateRequest(BaseModel):
    document_number: str | None = None
    document_type: str | None = Field(None, max_length=50)
    document_type_other: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None


class DocumentBatchPhotosRequest(BaseModel):
    document_ids: list[UUID]

    @field_validator("document_ids")
    @classmethod
    def validate_count(cls, v: list[UUID]) -> list[UUID]:
        unique = list(set(v))
        if len(unique) > 50:
            raise ValueError("Maximum 50 document IDs allowed per request")
        return unique


class DocumentPhotoEntry(BaseModel):
    document_id: UUID
    front_photo_base64: str | None = None
    front_photo_mime: str | None = None
    back_photo_base64: str | None = None
    back_photo_mime: str | None = None


class DocumentBatchPhotosResponse(BaseModel):
    photos: list[DocumentPhotoEntry]


class ErrorResponse(BaseModel):
    detail: str
    hint: str | None = None
