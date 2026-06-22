"""Shared test fixtures and configuration."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from dhanada.auth.api import AuthManager
from dhanada.auth.auth.jwt import JWTManager
from dhanada.auth.auth.passwords import PasswordManager
from dhanada.auth.auth.totp import TOTPManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.crypto.envelope import EnvelopeEncryption
from dhanada.auth.crypto.keys import KEKManager
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.models import Base
from dhanada.auth.models.user import User
from dhanada.crm.services import ClientService, DocumentService


# Test configuration constants
def _generate_test_kek():
    mgr, b64 = KEKManager.generate()
    return b64, mgr


TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/dhanada_test",
)

TEST_JWT_SECRET = "test-secret-key-for-unit-tests-min-32-char!"  # noqa: S105
TEST_KEK_BASE64, TEST_KEK_MANAGER = _generate_test_kek()


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, Any, None]:
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with clean tables."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS crm"))
        await conn.commit()
        await conn.run_sync(Base.metadata.create_all)

    db = DatabaseSession(TEST_DATABASE_URL)
    async with db.session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
        await conn.execute(text("DROP SCHEMA IF EXISTS crm CASCADE"))
        await conn.commit()
    await engine.dispose()


@pytest.fixture
def jwt_manager() -> JWTManager:
    """Create a test JWT manager."""
    return JWTManager(
        secret_key=TEST_JWT_SECRET,
        algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def password_manager() -> PasswordManager:
    """Create a test password manager."""
    return PasswordManager()


@pytest.fixture
def kek_manager() -> KEKManager:
    """Create a test KEK manager."""
    return TEST_KEK_MANAGER


@pytest.fixture
def envelope_encryption(kek_manager: KEKManager) -> EnvelopeEncryption:
    """Create a test envelope encryption instance."""
    return EnvelopeEncryption(kek_manager)


@pytest.fixture
def totp_manager(envelope_encryption: EnvelopeEncryption) -> TOTPManager:
    """Create a test TOTP manager."""
    return TOTPManager(
        encryption=envelope_encryption,
        issuer="Dhanada Test",
        window=1,
    )


@pytest.fixture
def auth_config() -> AuthConfig:
    """Create a test auth config."""
    return AuthConfig(
        database_url=TEST_DATABASE_URL,
        jwt_secret_key=TEST_JWT_SECRET,
        kek_base64=TEST_KEK_BASE64,
    )  # type: ignore[call-arg]


@pytest.fixture
async def auth_manager(auth_config: AuthConfig) -> AsyncGenerator[AuthManager, None]:
    """Create a test AuthManager with clean DB."""
    auth = AuthManager(auth_config)
    try:
        yield auth
    finally:
        await auth.close()


@pytest_asyncio.fixture
async def test_user(auth_manager: AuthManager) -> User:
    """Create a test user with superuser rights for service tests."""
    user = await auth_manager.register_user(
        email="services.test@example.com",
        username="servicestest",
        password="ServiceTest123!",  # noqa: S106
        full_name="Service Test User",
    )
    return user


@pytest_asyncio.fixture
async def client_service(auth_manager: AuthManager, _test_user: User) -> ClientService:
    """Create a ClientService with its own DB session."""
    from dhanada.auth.db.session import DatabaseSession

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        yield ClientService(
            session=session,
            auth=auth_manager,
            envelope=auth_manager._envelope,
        )


@pytest_asyncio.fixture
async def document_service(auth_manager: AuthManager, _test_user: User) -> DocumentService:
    """Create a DocumentService with its own DB session."""
    from dhanada.auth.db.session import DatabaseSession

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        yield DocumentService(
            session=session,
            auth=auth_manager,
            envelope=auth_manager._envelope,
        )


# Shared test data
TEST_USER_EMAIL = "test@example.com"
TEST_USER_USERNAME = "testuser"
TEST_USER_PASSWORD = "SecurePassword123!"  # noqa: S105
TEST_USER_FULL_NAME = "Test User"
