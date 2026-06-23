"""Shared test fixtures and configuration."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from dotenv import load_dotenv
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

load_dotenv()

# Test configuration constants
def _generate_test_kek():
    mgr, b64 = KEKManager.generate()
    return b64, mgr


def _get_database_url() -> str:
    """Resolve the test database URL.

    Priority:
    1. ``TEST_DATABASE_URL`` env var → user-provided connection string.
    2. Fallback to ``localhost:5432/dhanada_test``.
    """
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/dhanada_test",
    )


TEST_DATABASE_URL = _get_database_url()

TEST_JWT_SECRET = "test-secret-key-for-unit-tests-min-32-char!"  # noqa: S105
TEST_KEK_BASE64, TEST_KEK_MANAGER = _generate_test_kek()


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, Any, None]:
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def _test_database_url() -> Generator[str, Any, None]:
    """Provide the database URL, optionally via testcontainers.

    Set ``TESTCONTAINERS=1`` or run in CI to automatically start a disposable
    PostgreSQL 16 container instead of using a pre-configured database.

    Requires ``testcontainers`` (dev dependency) and Docker.
    """
    if not (os.getenv("TESTCONTAINERS") or os.getenv("CI")):
        yield _get_database_url()
        return

    try:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
    except ImportError:
        msg = (
            "TESTCONTAINERS=1 or CI=true requires the testcontainers package. "
            "Install it with: pip install testcontainers"
        )
        raise RuntimeError(msg) from None  # noqa: TRY004

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    sync_url = container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    yield async_url
    container.stop()


@pytest_asyncio.fixture(scope="session")
async def _ensure_tables(
    _test_database_url: str,
) -> AsyncGenerator[None, None]:
    """Create schemas and tables once per session.

    Not autouse — only fires when requested by a downstream conftest
    or by ``db_session``. This avoids connecting to the database for
    unit tests that do not need it.
    """
    engine = create_async_engine(_test_database_url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
        await conn.execute(text("DROP SCHEMA IF EXISTS crm CASCADE"))
        await conn.execute(text("CREATE SCHEMA auth"))
        await conn.execute(text("CREATE SCHEMA crm"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
        await conn.execute(text("DROP SCHEMA IF EXISTS crm CASCADE"))
    await engine.dispose()


@pytest_asyncio.fixture
async def _clean_tables(
    _test_database_url: str,
) -> AsyncGenerator[None, None]:
    """Truncate all tables before each test for isolation.

    Not autouse — only fires when requested by a downstream conftest.
    This avoids connecting to the database for unit tests that do not
    need it.
    """
    engine = create_async_engine(_test_database_url)
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()
    yield


@pytest_asyncio.fixture(scope="session")
async def db_session(
    _test_database_url: str,
    _ensure_tables: None,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with clean tables.

    Depends on ``_ensure_tables`` so that schemas and tables exist
    before the session is created.
    """
    db = DatabaseSession(_test_database_url)
    async with db.session() as session:
        yield session


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
        zeptomail_api_key="test-zeptomail-key",
        zeptomail_from_email="test@dhanada.app",
        pan_hmac_key="test-pan-hmac-key-min-16-chars",
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
async def test_user(auth_manager: AuthManager, request: pytest.FixtureRequest) -> User:
    """Create a test superuser for service tests."""
    import uuid
    suffix = uuid.uuid4().hex[:8]
    user = await auth_manager.register_user(
        email=f"services.{suffix}@example.com",
        username=f"servicestest_{suffix}",
        password="ServiceTest123!",
        full_name="Service Test User",
    )
    from dhanada.auth.db.repository import UserRepository
    from dhanada.auth.db.session import DatabaseSession
    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        repo = UserRepository(session)
        await repo.update(user.id, is_superuser=True)
    await db.close()
    return user


@pytest_asyncio.fixture
async def client_service(auth_manager: AuthManager) -> ClientService:
    """Create a ClientService with its own DB session."""
    from dhanada.auth.db.session import DatabaseSession

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        yield ClientService(
            session=session,
            auth=auth_manager,
            envelope=auth_manager.envelope,
        )


@pytest_asyncio.fixture
async def document_service(auth_manager: AuthManager) -> DocumentService:
    """Create a DocumentService with its own DB session."""
    from dhanada.auth.db.session import DatabaseSession

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        yield DocumentService(
            session=session,
            auth=auth_manager,
            envelope=auth_manager.envelope,
        )


# Shared test data
TEST_USER_EMAIL = "test@example.com"
TEST_USER_USERNAME = "testuser"
TEST_USER_PASSWORD = "SecurePassword123!"  # noqa: S105
TEST_USER_FULL_NAME = "Test User"
