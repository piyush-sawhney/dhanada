"""Fixtures for auth integration tests using FastAPI TestClient."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dhanada.auth.api import AuthManager
from dhanada.auth.db.repository import RefreshTokenRepository, UserRepository
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.fastapi.router import auth_router
from dhanada.auth.services.token_service import TokenService

SUPERUSER_EMAIL = "super@test.com"
SUPERUSER_PASSWORD = "SuperSecret123!"  # noqa: S105


@pytest_asyncio.fixture
async def app(auth_manager: AuthManager) -> FastAPI:
    """Create a FastAPI app for testing."""
    application = FastAPI()
    application.include_router(auth_router, prefix="/api/auth")
    application.state.auth_manager = auth_manager
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def superuser(
    auth_manager: AuthManager,
) -> object:
    """Create a superuser and return its ID."""

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        user_repo = UserRepository(session)
        existing = await user_repo.get_by_email(SUPERUSER_EMAIL)
        if existing:
            return existing

        user = await user_repo.create(
            email=SUPERUSER_EMAIL,
            username="super",
            password_hash=auth_manager._password_manager.hash_password(SUPERUSER_PASSWORD),
            full_name="Super User",
            is_active=True,
            is_superuser=True,
        )
        await session.commit()
        return user


@pytest_asyncio.fixture
async def superuser_token(
    auth_manager: AuthManager,
    superuser: object,
) -> str:
    """Get an access token for the superuser (bypasses TOTP)."""

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        user_repo = UserRepository(session)
        token_repo = RefreshTokenRepository(session)
        token_service = TokenService(token_repo, user_repo, auth_manager._jwt)

        result = await token_service.create_tokens(
            user_id=superuser.id,
        )
        return result.access_token
