"""Integration tests for email verification flow."""


import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestEmailVerification:
    """Tests for send-verification and verify-email endpoints."""

    async def test_send_verification_requires_auth(
        self, client: AsyncClient
    ):
        """POST /send-verification without auth should return 401."""
        resp = await client.post("/api/auth/send-verification")
        assert resp.status_code == 401

    async def test_send_verification_succeeds(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /send-verification with auth should return success."""
        resp = await client.post(
            "/api/auth/send-verification",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sent" in data

    async def test_verify_email_with_valid_token(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """GET /verify-email with valid token should verify email."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        token = auth_manager._jwt.create_verification_token(user.id, ttl_minutes=60)
        resp = await client.get(f"/api/auth/verify-email?token={token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["email"] == "super@test.com"

    async def test_verify_email_with_invalid_token(
        self, client: AsyncClient
    ):
        """GET /verify-email with invalid token should return 400."""
        resp = await client.get(
            "/api/auth/verify-email?token=invalid-token-here"
        )
        assert resp.status_code == 400

    async def test_verify_email_with_expired_token(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """GET /verify-email with expired token should return 400."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        token = auth_manager._jwt.create_verification_token(user.id, ttl_minutes=-1)
        resp = await client.get(f"/api/auth/verify-email?token={token}")
        assert resp.status_code == 400
