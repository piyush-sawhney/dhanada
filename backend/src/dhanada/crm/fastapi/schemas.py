"""Pydantic schemas for CRM API."""

import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from dhanada.crm.models import DocumentType

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class ClientCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    pan: str = Field(..., min_length=10, max_length=10)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        normalized = v.upper().strip()
        if not PAN_PATTERN.match(normalized):
            raise ValueError("PAN must match format: AAAAA1234A (5 letters, 4 digits, 1 letter)")
        return normalized


class ClientUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class ClientPanUpdateRequest(BaseModel):
    pan: str = Field(..., min_length=10, max_length=10)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        normalized = v.upper().strip()
        if not PAN_PATTERN.match(normalized):
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


class ClientListParams(BaseModel):
    search: str | None = Field(None, max_length=255)
    include_inactive: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class DocumentCreateRequest(BaseModel):
    client_id: UUID
    document_number: str | None = Field(None, max_length=100)
    document_type: str = Field(..., max_length=50)
    document_type_other: str | None = Field(None, max_length=255)
    issue_date: date
    expiry_date: date | None = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        valid = {t.value for t in DocumentType}
        if v not in valid:
            raise ValueError(f"Invalid document type. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("document_type_other")
    @classmethod
    def validate_other_required(cls, v: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("document_type") == "other" and not v:
            raise ValueError("document_type_other is required when document_type is 'other'")
        return v


class DocumentResponse(BaseModel):
    id: UUID
    client_id: UUID
    document_number: str | None
    document_type: str
    document_type_other: str | None
    issue_date: date
    expiry_date: date | None
    has_front_photo: bool
    has_back_photo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_document(cls, doc: Any) -> "DocumentResponse":
        return cls(
            id=doc.id,
            client_id=doc.client_id,
            document_number=doc.document_number,
            document_type=doc.document_type,
            document_type_other=doc.document_type_other,
            issue_date=doc.issue_date,
            expiry_date=doc.expiry_date,
            has_front_photo=doc.front_photo_data is not None,
            has_back_photo=doc.back_photo_data is not None,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class DocumentUpdateRequest(BaseModel):
    document_number: str | None = None
    document_type: str | None = Field(None, max_length=50)
    document_type_other: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid = {t.value for t in DocumentType}
        if v not in valid:
            raise ValueError(f"Invalid document type. Must be one of: {', '.join(sorted(valid))}")
        return v


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
