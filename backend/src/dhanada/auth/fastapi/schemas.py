"""Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_token: str | None = Field(None, min_length=6, max_length=16)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int = 900


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class TOTPEnableResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str] | None = None


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
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")


class AssignRoleRequest(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=50)


class PermissionCheckResponse(BaseModel):
    allowed: bool
    resource: str
    action: str


class BootstrapRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=200)


class BootstrapStatusResponse(BaseModel):
    needs_bootstrap: bool


class ErrorResponse(BaseModel):
    detail: str
    hint: str | None = None


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    full_name: str | None = Field(None, max_length=200)
    role_name: str | None = Field(None, min_length=1, max_length=50)


class UserCreatedResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool = False
    is_superuser: bool = False
    temporary_password: str
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BootstrapCompleteResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int = 900
    totp_required: bool = True


class SetupRequiredResponse(BaseModel):
    status: str = "setup_required"
    setup_token: str
    expires_in: int = 900


class SetupCompleteRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminResetUserAuthResponse(BaseModel):
    temporary_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    verified: bool
    email: str | None = None


class SendVerificationRequest(BaseModel):
    email: str | None = None


class SendVerificationResponse(BaseModel):
    sent: bool
    message: str = "If the email exists, a verification email has been sent."


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    per_page: int


class AdminUpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    full_name: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class UserDeleteResponse(BaseModel):
    deleted: bool


class RolePermissionResponse(BaseModel):
    resource: str
    action: str


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[RolePermissionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    roles: list[RoleResponse]


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)


class RevokeRoleRequest(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=50)


class AddPermissionRequest(BaseModel):
    resource: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=50)
