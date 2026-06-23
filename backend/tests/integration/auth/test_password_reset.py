"""Integration tests for password reset flow."""


import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestPasswordReset:
    """Tests for forgot-password and reset-password endpoints."""

    async def test_forgot_password_always_succeeds(
        self, client: AsyncClient
    ):
        """POST /forgot-password should always return success (prevents enumeration)."""
        resp = await client.post(
            "/api/auth/forgot-password",
            json={"email": "nonexistent@test.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] is True

    @pytest.mark.usefixtures("superuser")
    async def test_forgot_password_with_valid_email(
        self, client: AsyncClient
    ):
        """POST /forgot-password with valid email should return success."""
        resp = await client.post(
            "/api/auth/forgot-password",
            json={"email": "super@test.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] is True

    async def test_reset_password_with_invalid_token(
        self, client: AsyncClient
    ):
        """POST /reset-password with invalid token should return 400."""
        resp = await client.post(
            "/api/auth/reset-password",
            json={
                "token": "invalid-reset-token",
                "new_password": "NewSecurePass123!",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.usefixtures("superuser")
    async def test_reset_password_with_valid_token(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """POST /reset-password with valid token should reset password."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        token = auth_manager._jwt.create_reset_token(
            user.id, ttl_minutes=60, version=user.password_reset_version
        )
        resp = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "NewSecurePass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @pytest.mark.usefixtures("superuser")
    async def test_reset_password_token_is_single_use(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """Reset token should be single-use - second attempt should fail."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        token = auth_manager._jwt.create_reset_token(
            user.id, ttl_minutes=60, version=user.password_reset_version
        )

        resp1 = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "AnotherPass123!"},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["success"] is True

        # Second attempt with same token should fail
        resp2 = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "YetAnotherPass456!"},
        )
        assert resp2.status_code == 400
