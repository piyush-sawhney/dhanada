"""Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_token: str | None = Field(None, min_length=6, max_length=16)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class TOTPEnableResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    token: str = Field(..., min_length=6, max_length=16)


class TOTPDisableRequest(BaseModel):
    token: str = Field(..., min_length=6, max_length=16)


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    email_verified: bool
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(None, max_length=200)


class AssignRoleRequest(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=50)


class PermissionCheckResponse(BaseModel):
    allowed: bool
    resource: str
    action: str


class ErrorResponse(BaseModel):
    detail: str
    hint: str | None = None