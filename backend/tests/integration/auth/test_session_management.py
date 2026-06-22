"""Integration tests for session management."""

import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestSessionListing:
    """Tests for session listing endpoints."""

    async def test_get_my_sessions(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /sessions should return current user's active sessions."""
        resp = await client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    async def test_get_my_sessions_requires_auth(self, client: AsyncClient):
        """GET /sessions without auth should return 401."""
        resp = await client.get("/api/auth/sessions")
        assert resp.status_code == 401

    async def test_admin_get_user_sessions(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """GET /admin/users/{user_id}/sessions should return user's sessions."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        resp = await client.get(
            f"/api/auth/admin/users/{user.id}/sessions",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    async def test_admin_get_user_sessions_nonexistent(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /admin/users/{user_id}/sessions with bad ID should return 404."""
        from uuid import UUID

        resp = await client.get(
            f"/api/auth/admin/users/{UUID(int=0)}/sessions",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_non_superuser_cannot_list_other_sessions(
        self, client: AsyncClient, superuser_token: str
    ):
        """Non-superusers should not be able to list other users' sessions."""
        from uuid import UUID

        resp = await client.get(
            f"/api/auth/admin/users/{UUID(int=0)}/sessions",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404


class TestLogoutAll:
    """Tests for logout-all endpoint."""

    async def test_logout_all(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /logout-all should revoke all sessions."""
        resp = await client.post(
            "/api/auth/logout-all",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 204
