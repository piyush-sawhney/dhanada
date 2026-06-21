"""FastAPI integration for authentication."""

from dhanada.auth.fastapi.dependencies import (
    get_auth_manager,
    get_current_user,
    require_permission,
    require_roles,
    require_superuser,
)
from dhanada.auth.fastapi.router import auth_router

__all__ = [
    "get_auth_manager",
    "get_current_user",
    "require_permission",
    "require_roles",
    "require_superuser",
    "auth_router",
]