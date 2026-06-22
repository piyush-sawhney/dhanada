"""FastAPI dependency injection for authentication.

Usage in FastAPI app::

    from fastapi import FastAPI, Depends
    from dhanada.auth.fastapi import (
        get_auth_manager,
        get_current_user,
        require_permission,
        auth_router,
    )
    from dhanada.auth.models import User

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    @app.get("/users/me")
    async def get_me(user: User = Depends(get_current_user)):
        return {"id": str(user.id), "email": user.email}

    @app.delete("/users/{user_id}")
    async def delete_user(
        user_id: UUID,
        _=Depends(require_permission("users", "delete")),
    ):
        ...
"""

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dhanada.auth.api import AuthManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    PermissionDeniedError,
    TokenExpiredError,
)
from dhanada.auth.models.user import User

security = HTTPBearer(auto_error=False)


async def get_auth_manager() -> AsyncGenerator[AuthManager, None]:
    """Dependency that provides an AuthManager instance.

    Initialized from AuthConfig (reads environment variables).
    """
    config = AuthConfig()  # type: ignore[call-arg]
    auth = AuthManager(config)
    try:
        yield auth
    finally:
        await auth.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth: AuthManager = Depends(get_auth_manager),
) -> User:
    """Dependency that extracts and validates the current user from JWT.

    Expects a Bearer token in the Authorization header.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = auth._jwt.verify_access_token(credentials.credentials)
        user = await auth.get_user(UUID(payload.sub))
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )


def require_permission(resource: str, action: str):
    """Dependency factory that requires a specific permission.

    Usage::

        @app.delete("/items/{item_id}")
        async def delete_item(
            _=Depends(require_permission("items", "delete")),
        ):
            ...
    """

    async def permission_checker(
        user: User = Depends(get_current_user),
        auth: AuthManager = Depends(get_auth_manager),
    ) -> None:
        try:
            await auth.check_permission(user.id, resource, action)
        except PermissionDeniedError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )

    return permission_checker


def require_roles(*roles: str):
    """Dependency factory that requires specific roles.

    Usage::

        @app.get("/admin")
        async def admin_panel(
            _=Depends(require_roles("admin")),
        ):
            ...
    """

    async def role_checker(
        user: User = Depends(get_current_user),
        auth: AuthManager = Depends(get_auth_manager),
    ) -> None:
        user_roles = await auth.get_user_roles(user.id)
        for role in roles:
            if role not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires role: {role}",
                )

    return role_checker


async def require_superuser(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency that requires a superuser."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user


async def require_setup_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth: AuthManager = Depends(get_auth_manager),
) -> User:
    """Dependency that validates a setup token and returns the user.

    Setup tokens are short-lived JWTs (15 min) with type='setup'.
    Used during first-time login flow and admin-forced resets.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = auth._jwt.verify_setup_token(credentials.credentials)
        user = await auth.get_user(UUID(payload.sub))
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Setup token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid setup token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )


async def get_setup_or_active_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth: AuthManager = Depends(get_auth_manager),
) -> User:
    """Dependency that accepts either a setup token or a regular JWT.

    Tries setup token first (for inactive users during first-time flow),
    then falls back to regular authentication (for active users).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try setup token first
    try:
        payload = auth._jwt.verify_setup_token(credentials.credentials)
        return await auth.get_user(UUID(payload.sub))
    except (InvalidTokenError, TokenExpiredError, AuthenticationError):
        pass

    # Fall back to regular access token
    try:
        payload = auth._jwt.verify_access_token(credentials.credentials)
        user = await auth.get_user(UUID(payload.sub))
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )