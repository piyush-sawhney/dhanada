"""FastAPI router for authentication endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from dhanada.auth.api import AuthManager
from dhanada.auth.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    PermissionDeniedError,
    TOTPAlreadyEnabledError,
    TOTPError,
    TOTPInvalidTokenError,
    TOTPNotEnabledError,
    TokenExpiredError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from dhanada.auth.fastapi.dependencies import (
    get_auth_manager,
    get_current_user,
    require_permission,
    require_superuser,
)
from dhanada.auth.fastapi.schemas import (
    AssignRoleRequest,
    ChangePasswordRequest,
    ErrorResponse,
    LoginRequest,
    PermissionCheckResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    TOTPDisableRequest,
    TOTPEnableResponse,
    TOTPVerifyRequest,
    TokenResponse,
    UserResponse,
)
from dhanada.auth.models.user import User

auth_router = APIRouter(tags=["auth"])


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and user agent from request."""
    user_agent = request.headers.get("user-agent")
    forwarded = request.headers.get("x-forwarded-for")
    ip_address = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else None
    return user_agent, ip_address


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def register(
    body: RegisterRequest,
    auth: AuthManager = Depends(get_auth_manager),
) -> UserResponse:
    """Register a new user."""
    try:
        user = await auth.register_user(
            email=body.email,
            username=body.username,
            password=body.password,
            full_name=body.full_name,
        )
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            email_verified=user.email_verified,
            roles=[r.name for r in user.roles],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def login(
    body: LoginRequest,
    request: Request,
    auth: AuthManager = Depends(get_auth_manager),
) -> TokenResponse:
    """Login with email and password, optionally with TOTP."""
    try:
        user_agent, ip_address = _get_client_info(request)
        result = await auth.authenticate(
            email=body.email,
            password=body.password,
            totp_token=body.totp_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except (TOTPNotEnabledError, TOTPInvalidTokenError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@auth_router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
async def refresh(
    body: RefreshRequest,
    request: Request,
    auth: AuthManager = Depends(get_auth_manager),
) -> TokenResponse:
    """Refresh access token using a refresh token."""
    try:
        user_agent, ip_address = _get_client_info(request)
        result = await auth.refresh_session(
            refresh_token=body.refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )
    except (InvalidTokenError, TokenExpiredError, AuthenticationError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    auth: AuthManager = Depends(get_auth_manager),
) -> None:
    """Revoke a refresh token."""
    await auth.revoke_session(body.refresh_token)


@auth_router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> None:
    """Revoke all refresh tokens for the current user."""
    await auth.revoke_all_sessions(user.id)


@auth_router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> UserResponse:
    """Get current user profile."""
    user = await auth.get_user(user.id)
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        email_verified=user.email_verified,
        roles=[r.name for r in user.roles],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@auth_router.patch(
    "/me",
    response_model=UserResponse,
)
async def update_me(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> UserResponse:
    """Update current user profile."""
    updated = await auth.update_profile(user.id, full_name=body.full_name)
    return UserResponse(
        id=updated.id,
        email=updated.email,
        username=updated.username,
        full_name=updated.full_name,
        is_active=updated.is_active,
        is_superuser=updated.is_superuser,
        email_verified=updated.email_verified,
        roles=[r.name for r in updated.roles],
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> None:
    """Change current user's password."""
    try:
        await auth.change_password(user.id, body.old_password, body.new_password)
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@auth_router.post(
    "/totp/enable",
    response_model=TOTPEnableResponse,
    responses={409: {"model": ErrorResponse}},
)
async def enable_totp(
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> TOTPEnableResponse:
    """Enable TOTP two-factor authentication."""
    try:
        result = await auth.enable_totp(user.id)
        return TOTPEnableResponse(
            secret=result.secret,
            provisioning_uri=result.provisioning_uri,
            backup_codes=result.backup_codes,
        )
    except TOTPAlreadyEnabledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@auth_router.post(
    "/totp/verify",
    status_code=status.HTTP_200_OK,
)
async def verify_totp(
    body: TOTPVerifyRequest,
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> dict:
    """Verify and confirm TOTP enrollment."""
    try:
        verified = await auth.verify_and_confirm_totp(user.id, body.token)
        return {"verified": verified}
    except TOTPError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@auth_router.post(
    "/totp/disable",
    status_code=status.HTTP_200_OK,
    responses={400: {"model": ErrorResponse}},
)
async def disable_totp(
    body: TOTPDisableRequest,
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> dict:
    """Disable TOTP two-factor authentication."""
    try:
        disabled = await auth.disable_totp(user.id, body.token)
        return {"disabled": disabled}
    except TOTPError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@auth_router.post(
    "/totp/backup-codes",
    status_code=status.HTTP_200_OK,
)
async def generate_backup_codes(
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> dict:
    """Generate new backup codes (invalidates old ones)."""
    codes = await auth.generate_backup_codes(user.id)
    return {"backup_codes": codes}


@auth_router.post(
    "/roles",
    status_code=status.HTTP_200_OK,
)
async def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    _=Depends(require_permission("roles", "assign")),
    auth: AuthManager = Depends(get_auth_manager),
) -> dict:
    """Assign a role to a user. Requires roles:assign permission."""
    assigned = await auth.assign_role(user_id, body.role_name)
    return {"assigned": assigned}


@auth_router.get(
    "/roles",
    response_model=list[str],
)
async def get_roles(
    user_id: UUID,
    _=Depends(require_permission("roles", "read")),
    auth: AuthManager = Depends(get_auth_manager),
) -> list[str]:
    """Get roles for a user. Requires roles:read permission."""
    return await auth.get_user_roles(user_id)


@auth_router.get(
    "/permissions/check",
    response_model=PermissionCheckResponse,
)
async def check_permission(
    resource: str,
    action: str,
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> PermissionCheckResponse:
    """Check if the current user has a specific permission."""
    result = await auth.check_permission(user.id, resource, action)
    return PermissionCheckResponse(
        allowed=result.allowed,
        resource=result.resource,
        action=result.action,
    )


@auth_router.get(
    "/permissions",
    response_model=list[str],
)
async def get_permissions(
    user: User = Depends(get_current_user),
    auth: AuthManager = Depends(get_auth_manager),
) -> list[str]:
    """Get all permissions for the current user."""
    return await auth.get_user_permissions(user.id)


@auth_router.get(
    "/users/{user_id}",
    response_model=UserResponse,
)
async def get_user(
    user_id: UUID,
    _=Depends(require_permission("users", "read")),
    auth: AuthManager = Depends(get_auth_manager),
) -> UserResponse:
    """Get a user by ID. Requires users:read permission."""
    try:
        user = await auth.get_user(user_id)
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            email_verified=user.email_verified,
            roles=[r.name for r in user.roles],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")