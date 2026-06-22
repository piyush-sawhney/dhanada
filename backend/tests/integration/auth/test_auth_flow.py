"""Integration tests for core authentication flows."""

import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager
from dhanada.auth.models.user import User

pytestmark = pytest.mark.asyncio


class TestBootstrapFlow:
    """Tests for the bootstrap (first superuser) flow."""

    async def test_bootstrap_status_needed(self, client: AsyncClient, auth_manager: AuthManager):
        """GET /bootstrap/status should return needs_bootstrap when no users exist."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            repo = UserRepository(session)
            count = await repo.count()
            if count > 0:
                pytest.skip("Users already exist in the database")

        resp = await client.get("/api/auth/bootstrap/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_bootstrap"] is True

    async def test_bootstrap_creates_superuser(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """POST /bootstrap should create the first superuser and return tokens."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            repo = UserRepository(session)
            count = await repo.count()
            if count > 0:
                pytest.skip("Users already exist - bootstrap blocked")

        resp = await client.post(
            "/api/auth/bootstrap",
            json={
                "email": "bootstrap@test.com",
                "username": "bootstrap",
                "password": "BootstrapPass123!",
                "full_name": "Bootstrap User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "bootstrap@test.com"
        assert data["user"]["is_superuser"] is True

    async def test_bootstrap_fails_when_users_exist(
        self, client: AsyncClient, superuser: User  # noqa: ARG002
    ):
        """POST /bootstrap should fail with 409 when users already exist."""
        resp = await client.post(
            "/api/auth/bootstrap",
            json={
                "email": "another@test.com",
                "username": "another",
                "password": "BootstrapPass123!",
                "full_name": "Another User",
            },
        )
        assert resp.status_code == 409


class TestLoginFlow:
    """Tests for the login flow."""

    async def test_login_inactive_user_returns_setup_token(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """Login as inactive user should return a setup token."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            await user_repo.create(
                email="inactive-login@test.com",
                username="inactivelogin",
                password_hash=auth_manager._password_manager.hash_password("TestPass123!"),
                full_name="Inactive Login",
                is_active=False,
            )
            await session.commit()

        resp = await client.post(
            "/api/auth/login",
            json={"email": "inactive-login@test.com", "password": "TestPass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "setup_required"
        assert "setup_token" in data

    async def test_login_with_invalid_credentials_returns_401(
        self, client: AsyncClient
    ):
        """Login with wrong password should return 401."""
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "WrongPassword123!"},
        )
        assert resp.status_code == 401


class TestRefreshFlow:
    """Tests for token refresh flow."""

    async def test_refresh_with_valid_token(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager  # noqa: ARG002
    ):
        """POST /refresh with valid refresh token should return new tokens."""
        from dhanada.auth.db.repository import RefreshTokenRepository, UserRepository
        from dhanada.auth.db.session import DatabaseSession
        from dhanada.auth.services.token_service import TokenService

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            token_service = TokenService(token_repo, user_repo, auth_manager._jwt)

            tokens = await token_service.create_tokens(
                user_id=(await user_repo.get_by_email("super@test.com")).id,
            )

        resp = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens.refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105

    async def test_refresh_with_invalid_token_returns_401(
        self, client: AsyncClient
    ):
        """POST /refresh with invalid token should return 401."""
        resp = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token-here"},
        )
        assert resp.status_code == 401


class TestLogoutFlow:
    """Tests for logout flows."""

    async def test_logout_revokes_token(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager  # noqa: ARG002
    ):
        """POST /logout should revoke the refresh token."""
        from dhanada.auth.db.repository import RefreshTokenRepository, UserRepository
        from dhanada.auth.db.session import DatabaseSession
        from dhanada.auth.services.token_service import TokenService

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            token_service = TokenService(token_repo, user_repo, auth_manager._jwt)

            tokens = await token_service.create_tokens(
                user_id=(await user_repo.get_by_email("super@test.com")).id,
            )

        resp = await client.post(
            "/api/auth/logout",
            json={"refresh_token": tokens.refresh_token},
        )
        assert resp.status_code == 204
