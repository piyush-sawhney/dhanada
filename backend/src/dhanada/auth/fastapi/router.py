"""FastAPI router for authentication endpoints."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from dhanada.auth.api import AuthManager
from dhanada.auth.exceptions import (
    AccountLockedError,
    AuthenticationError,
    CannotDeleteSystemRoleError,
    InvalidCredentialsError,
    InvalidTokenError,
    SuperuserAlreadyExistsError,
    TokenExpiredError,
    TOTPAlreadyEnabledError,
    TOTPError,
    TOTPInvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from dhanada.auth.fastapi.dependencies import (
    get_auth_manager,
    get_current_user,
    get_setup_or_active_user,
    require_permission,
    require_setup_token,
    require_superuser,
)
from dhanada.auth.fastapi.schemas import (
    AddPermissionRequest,
    AdminCreateUserRequest,
    AdminResetUserAuthResponse,
    AdminUpdateUserRequest,
    AssignRoleRequest,
    BootstrapCompleteResponse,
    BootstrapRequest,
    BootstrapStatusResponse,
    ChangePasswordRequest,
    CreateRoleRequest,
    ErrorResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    PermissionCheckResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterUserAppRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    RevokeRoleRequest,
    RoleListResponse,
    RolePermissionResponse,
    RoleResponse,
    SendVerificationResponse,
    SessionListResponse,
    SessionResponse,
    SetupCompleteRequest,
    SetupRequiredResponse,
    TokenResponse,
    TOTPDisableRequest,
    TOTPEnableResponse,
    TOTPVerifyRequest,
    UnregisterUserAppRequest,
    UserAppListResponse,
    UserCreatedResponse,
    UserDeleteResponse,
    UserListResponse,
    UserResponse,
    VerifyEmailResponse,
)
from dhanada.auth.models.user import User
from dhanada.auth.rate_limit import limiter

auth_router = APIRouter(tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    """Convert a User model to a UserResponse schema."""
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


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and user agent from request."""
    user_agent = request.headers.get("user-agent")
    forwarded = request.headers.get("x-forwarded-for")
    ip_address = (
        forwarded.split(",")[0].strip()
        if forwarded
        else request.client.host
        if request.client
        else None
    )
    return user_agent, ip_address


@auth_router.post(
    "/register",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def register(
    body: AdminCreateUserRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    _: object = Depends(require_permission("users", "create")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserCreatedResponse:
    """Register a new user. Requires users:create permission.

    Creates the user as inactive with a system-generated temporary password.
    The user must complete TOTP setup and password change on first login.
    Optionally assigns a role that becomes active after user activation.
    """
    try:
        temp_password = auth.generate_temp_password()
        new_user = await auth.register_user(
            email=body.email,
            username=body.username,
            password=temp_password,
            full_name=body.full_name,
            current_user_id=user.id,
            is_active=False,
        )

        roles: list[str] = []
        if body.role_name:
            ok = await auth.assign_role(new_user.id, body.role_name, current_user_id=user.id)
            if ok:
                roles.append(body.role_name)

        return UserCreatedResponse(
            id=new_user.id,
            email=new_user.email,
            username=new_user.username,
            full_name=new_user.full_name,
            is_active=False,
            is_superuser=new_user.is_superuser,
            temporary_password=temp_password,
            roles=roles,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at,
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None


@auth_router.post(
    "/bootstrap",
    response_model=BootstrapCompleteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
@limiter.limit("3/minute")
async def bootstrap(
    body: BootstrapRequest,
    request: Request,
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> BootstrapCompleteResponse:
    """Register the first superuser. Only works when no users exist.

    Returns auto-login tokens so the UI can immediately proceed to TOTP setup.
    """
    try:
        user = await auth.create_superuser(
            email=body.email,
            username=body.username,
            password=body.password,
            full_name=body.full_name,
        )
        user_agent, ip_address = _get_client_info(request)
        tokens = await auth._create_tokens(user, user_agent, ip_address)
        return BootstrapCompleteResponse(
            user=_user_to_response(user),
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            totp_required=True,
        )
    except SuperuserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None


@auth_router.get(
    "/bootstrap/status",
    response_model=BootstrapStatusResponse,
)
async def bootstrap_status(
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> BootstrapStatusResponse:
    """Check if the system needs bootstrapping (no users exist)."""
    return BootstrapStatusResponse(needs_bootstrap=not await auth.has_users())


@auth_router.post(
    "/login",
    response_model=TokenResponse | SetupRequiredResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
@limiter.limit("5/minute")
async def login(
    body: LoginRequest,
    request: Request,
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> TokenResponse | SetupRequiredResponse:
    """Login with email and password.

    Flow:
    1. If user is inactive → returns a 15-minute setup token for TOTP enrollment + activation.
    2. If user is active but TOTP not enabled → returns a setup token (bootstrap case).
    3. If user is active with TOTP → requires valid TOTP code, returns JWT tokens.
    """
    try:
        user_agent, ip_address = _get_client_info(request)
        user = await auth.verify_credentials(body.email, body.password)

        # Check if inactive account has expired
        if (
            not user.is_active
            and user.expires_at is not None
            and user.expires_at <= datetime.now(UTC)
        ):
            raise AuthenticationError(
                "Your account has expired. Please contact an administrator.",
                hint="A new account must be created by an administrator.",
            )

        # Setup flow for inactive users or users without TOTP
        if not user.is_active or not await auth.totp_is_enabled(user.id):
            setup_token = auth.generate_setup_token(user.id)
            return SetupRequiredResponse(setup_token=setup_token)

        # Normal login — TOTP is mandatory
        if body.totp_token is None or not await auth.verify_totp(user.id, body.totp_token):
            raise TOTPInvalidTokenError(
                "TOTP code required",
                hint="Provide your authenticator app code to complete login",
            )

        tokens = await auth._create_tokens(user, user_agent, ip_address)
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from None
    except AccountLockedError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from None
    except TOTPInvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from None
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from None


@auth_router.post(
    "/setup-complete",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
@limiter.limit("5/minute")
async def setup_complete(
    body: SetupCompleteRequest,
    request: Request,
    setup_user: User = Depends(require_setup_token),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> TokenResponse:
    """Complete first-time setup: set password, activate account, issue tokens.

    Requires a valid setup token (obtained from /login when setup is needed).
    The user must have already verified TOTP before calling this endpoint.

    For already-active users (e.g., bootstrap superuser after token expiry),
    the password is NOT changed and the account remains active — only
    new tokens are issued.
    """
    user_agent, ip_address = _get_client_info(request)
    tokens = await auth.complete_setup(
        user_id=setup_user.id,
        new_password=body.new_password,
        current_user_id=setup_user.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@auth_router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
async def refresh(
    body: RefreshRequest,
    request: Request,
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from None


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> None:
    """Revoke a refresh token."""
    await auth.revoke_session(body.refresh_token)


@auth_router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> None:
    """Revoke all refresh tokens for the current user."""
    await auth.revoke_all_sessions(user.id)


@auth_router.get(
    "/sessions",
    response_model=SessionListResponse,
)
async def get_my_sessions(
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> SessionListResponse:
    """Get all active sessions for the current user."""
    sessions = await auth.get_user_sessions(user.id)
    return SessionListResponse(
        sessions=[SessionResponse(**s) for s in sessions],
    )


@auth_router.get(
    "/admin/users/{user_id}/sessions",
    response_model=SessionListResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_user_sessions(
    user_id: UUID,
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> SessionListResponse:
    """Get all active sessions for a specific user. Requires superuser."""
    try:
        sessions = await auth.get_user_sessions(user_id)
        return SessionListResponse(
            sessions=[SessionResponse(**s) for s in sessions],
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from None


@auth_router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserResponse:
    """Get current user profile."""
    user = await auth.get_user(user.id)
    return _user_to_response(user)


@auth_router.patch(
    "/me",
    response_model=UserResponse,
    responses={409: {"model": ErrorResponse}},
)
async def update_me(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserResponse:
    """Update current user profile."""
    try:
        updated = await auth.update_profile(
            user.id,
            full_name=body.full_name,
            email=body.email,
            username=body.username,
            current_user_id=user.id,
        )
        return _user_to_response(updated)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> None:
    """Change current user's password."""
    try:
        await auth.change_password(
            user.id,
            body.old_password,
            body.new_password,
            current_user_id=user.id,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from None


@auth_router.post(
    "/totp/enable",
    response_model=TOTPEnableResponse,
    responses={409: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def enable_totp(
    request: Request,  # noqa: ARG001
    user: User = Depends(get_setup_or_active_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> TOTPEnableResponse:
    """Enable TOTP two-factor authentication.

    Works with both a regular JWT (active user, generates backup codes)
    and a setup token (first-time flow, no backup codes).
    """
    try:
        # Inactive user = setup flow = no backup codes
        generate_codes = user.is_active
        result = await auth.enable_totp(user.id, generate_backup_codes=generate_codes)
        return TOTPEnableResponse(
            secret=result.secret,
            provisioning_uri=result.provisioning_uri,
            backup_codes=result.backup_codes,
        )
    except TOTPAlreadyEnabledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None


@auth_router.post(
    "/totp/verify",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
async def verify_totp(
    body: TOTPVerifyRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_setup_or_active_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Verify and confirm TOTP enrollment.

    Works with both a regular JWT (active user) and a setup token (first-time flow).
    """
    try:
        verified = await auth.verify_and_confirm_totp(user.id, body.token)
        return {"verified": verified}
    except TOTPError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@auth_router.post(
    "/totp/disable",
    status_code=status.HTTP_200_OK,
    responses={400: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def disable_totp(
    body: TOTPDisableRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Disable TOTP two-factor authentication."""
    try:
        disabled = await auth.disable_totp(user.id, body.token)
        return {"disabled": disabled}
    except TOTPError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@auth_router.post(
    "/totp/backup-codes",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("3/minute")
async def generate_backup_codes(
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
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
    user: User = Depends(get_current_user),  # noqa: B008
    _: object = Depends(require_permission("roles", "assign")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Assign a role to a user. Requires roles:assign permission."""
    assigned = await auth.assign_role(
        user_id,
        body.role_name,
        current_user_id=user.id,
    )
    return {"assigned": assigned}


@auth_router.get(
    "/roles",
    response_model=list[str],
)
async def get_roles(
    user_id: UUID,
    _: object = Depends(require_permission("roles", "read")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
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
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
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
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> list[str]:
    """Get all permissions for the current user."""
    return await auth.get_user_permissions(user.id)


@auth_router.get(
    "/users/{user_id}",
    response_model=UserResponse,
)
async def get_user(
    user_id: UUID,
    _: object = Depends(require_permission("users", "read")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserResponse:
    """Get a user by ID. Requires users:read permission."""
    try:
        user = await auth.get_user(user_id)
        return _user_to_response(user)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@auth_router.post(
    "/admin/users/{user_id}/reset-auth",
    response_model=AdminResetUserAuthResponse,
    responses={404: {"model": ErrorResponse}},
)
async def admin_reset_user_auth(
    user_id: UUID,
    _user: User = Depends(require_superuser),  # noqa: B008  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008  # noqa: B008
) -> AdminResetUserAuthResponse:
    """Admin force-reset a user's authentication.

    Requires superuser.
    Disables TOTP, sets the user inactive, and generates a new temporary password.
    The user must go through the first-time login flow again.
    """
    try:
        temp_password = await auth.reset_user_auth(
            user_id=user_id,
            current_user_id=_user.id,
        )
        return AdminResetUserAuthResponse(temporary_password=temp_password)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@auth_router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def verify_email(
    token: str,
    request: Request,  # noqa: ARG001
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> VerifyEmailResponse:
    """Verify email address using a verification token."""
    try:
        result = await auth.verify_email(token)
        return VerifyEmailResponse(verified=result.verified, email=result.email)
    except (InvalidTokenError, TokenExpiredError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None


@auth_router.post(
    "/send-verification",
    response_model=SendVerificationResponse,
)
@limiter.limit("5/minute")
async def send_verification_email(
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> SendVerificationResponse:
    """Send a verification email to the current user."""
    sent = await auth.send_verification_email(user.id)
    return SendVerificationResponse(sent=sent)


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------


@auth_router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
)
@limiter.limit("3/minute")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,  # noqa: ARG001
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> ForgotPasswordResponse:
    """Request a password reset email.

    Always returns success to prevent email enumeration.
    If the email exists, a reset link is sent.
    """
    await auth.request_password_reset(body.email)
    return ForgotPasswordResponse()


@auth_router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,  # noqa: ARG001
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> ResetPasswordResponse:
    """Reset password using a reset token.

    The token is single-use. All existing sessions are revoked.
    TOTP enrollment and account active status are preserved.
    """
    try:
        result = await auth.reset_password(body.token, body.new_password)
        return ResetPasswordResponse(success=result.success, message=result.message)
    except (InvalidTokenError, TokenExpiredError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None


# ---------------------------------------------------------------------------
# Admin: User CRUD
# ---------------------------------------------------------------------------


@auth_router.get(
    "/users",
    response_model=UserListResponse,
)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserListResponse:
    """List all users with pagination and optional search. Requires superuser."""
    users, total = await auth.search_users(search, page, per_page)
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@auth_router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def admin_update_user(
    user_id: UUID,
    body: AdminUpdateUserRequest,
    user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserResponse:
    """Update any user's profile. Requires superuser."""
    try:
        updated = await auth.admin_update_user(
            user_id,
            email=body.email,
            username=body.username,
            full_name=body.full_name,
            is_active=body.is_active,
            current_user_id=user.id,
        )
        return _user_to_response(updated)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None


@auth_router.delete(
    "/users/{user_id}",
    response_model=UserDeleteResponse,
    responses={404: {"model": ErrorResponse}},
)
async def admin_delete_user(
    user_id: UUID,
    user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserDeleteResponse:
    """Soft-delete a user. Requires superuser."""
    try:
        deleted = await auth.delete_user(
            user_id,
            current_user_id=user.id,
        )
        return UserDeleteResponse(deleted=deleted)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


# ---------------------------------------------------------------------------
# Role CRUD
# ---------------------------------------------------------------------------


@auth_router.post(
    "/roles/create",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_role(
    body: CreateRoleRequest,
    user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> RoleResponse:
    """Create a new role. Requires superuser."""
    role = await auth.create_role(
        body.name,
        description=body.description,
        current_user_id=user.id,
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{body.name}' already exists",
        )
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            RolePermissionResponse(resource=p.resource, action=p.action) for p in role.permissions
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@auth_router.get(
    "/roles/all",
    response_model=RoleListResponse,
)
async def list_roles(
    _user: User = Depends(get_current_user),  # noqa: B008
    _: object = Depends(require_permission("roles", "read")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> RoleListResponse:
    """List all roles. Requires roles:read permission."""
    roles = await auth.list_roles()
    return RoleListResponse(
        roles=[
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                permissions=[
                    RolePermissionResponse(resource=p.resource, action=p.action)
                    for p in r.permissions
                ],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in roles
        ],
    )


@auth_router.delete(
    "/roles",
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}},
)
async def revoke_role(
    user_id: UUID,
    body: RevokeRoleRequest,
    _user: User = Depends(get_current_user),  # noqa: B008
    _: object = Depends(require_permission("roles", "assign")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Revoke a role from a user. Requires roles:assign permission."""
    revoked = await auth.revoke_role(user_id, body.role_name)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or role not found",
        )
    return {"revoked": True}


@auth_router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_role(
    role_id: UUID,
    user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Delete a role. Cannot delete system roles. Requires superuser."""
    try:
        deleted = await auth.delete_role(role_id, current_user_id=user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )
        return {"deleted": True}
    except CannotDeleteSystemRoleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@auth_router.get(
    "/roles/{role_name}",
    response_model=RoleResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_role(
    role_name: str,
    _user: User = Depends(get_current_user),  # noqa: B008
    _: object = Depends(require_permission("roles", "read")),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> RoleResponse:
    """Get a role with its permissions. Requires roles:read permission."""
    role = await auth.get_role_by_name(role_name)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' not found",
        )
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            RolePermissionResponse(resource=p.resource, action=p.action) for p in role.permissions
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@auth_router.post(
    "/roles/{role_name}/permissions",
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}},
)
async def add_permission_to_role(
    role_name: str,
    body: AddPermissionRequest,
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Add a permission to a role. Requires superuser."""
    added = await auth.add_permission_to_role(role_name, body.resource, body.action)
    if not added:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' not found",
        )
    return {"added": True}


@auth_router.delete(
    "/roles/{role_name}/permissions",
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}},
)
async def remove_permission_from_role(
    role_name: str,
    body: AddPermissionRequest,
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Remove a permission from a role. Requires superuser."""
    removed = await auth.remove_permission_from_role(role_name, body.resource, body.action)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' or permission not found",
        )
    return {"removed": True}


# ---------------------------------------------------------------------------
# Admin: App Membership
# ---------------------------------------------------------------------------


@auth_router.post(
    "/admin/apps/register",
    status_code=status.HTTP_200_OK,
)
async def register_user_to_app(
    body: RegisterUserAppRequest,
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Register a user to an app. Requires superuser."""
    registered = await auth.register_user_to_app(
        body.user_id,
        body.app_slug,
        assigned_by_id=_user.id,
    )
    if not registered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{body.app_slug}' not found",
        )
    return {"registered": True}


@auth_router.post(
    "/admin/apps/unregister",
    status_code=status.HTTP_200_OK,
)
async def unregister_user_from_app(
    body: UnregisterUserAppRequest,
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> dict[str, Any]:
    """Unregister a user from an app. Requires superuser."""
    unregistered = await auth.unregister_user_from_app(body.user_id, body.app_slug)
    if not unregistered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App or user-app association not found",
        )
    return {"unregistered": True}


@auth_router.get(
    "/admin/apps/users/{user_id}",
    response_model=UserAppListResponse,
)
async def get_user_apps(
    user_id: UUID,
    _user: User = Depends(require_superuser),  # noqa: B008
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> UserAppListResponse:
    """Get all registered apps for a user. Requires superuser."""
    app_slugs = await auth.get_user_apps(user_id)
    return UserAppListResponse(app_slugs=app_slugs)
