"""Integration tests for app membership (register/unregister) endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestAppMembership:
    """Tests for app registration, unregistration, and listing."""

    _APP_SLUG = "test-app"
    _ANOTHER_SLUG = "another-app"

    async def _create_app(self, auth_manager: AuthManager, slug: str) -> None:
        """Create an App record in the database if it doesn't exist."""
        from dhanada.auth.db.repository import AppRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            repo = AppRepository(session)
            existing = await repo.get_by_slug(slug)
            if existing is None:
                await repo.create(slug=slug, name=slug.replace("-", " ").title())
                await session.commit()

    async def _get_superuser_id(self, auth_manager: AuthManager) -> str:
        """Look up the superuser ID by email."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_email("super@test.com")
            assert user is not None
            return str(user.id)

    async def test_register_user_to_app(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """POST /api/auth/admin/apps/register should register a user to an app."""
        await self._create_app(auth_manager, self._APP_SLUG)
        user_id = await self._get_superuser_id(auth_manager)

        resp = await client.post(
            "/api/auth/admin/apps/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": self._APP_SLUG},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["registered"] is True

    async def test_register_nonexistent_app(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """POST /api/auth/admin/apps/register with bad slug should return 404."""
        user_id = await self._get_superuser_id(auth_manager)
        resp = await client.post(
            "/api/auth/admin/apps/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": "nonexistent-slug"},
        )
        assert resp.status_code == 404

    async def test_get_user_apps(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """GET /api/auth/admin/apps/users/{user_id} should list apps."""
        await self._create_app(auth_manager, self._APP_SLUG)
        await self._create_app(auth_manager, self._ANOTHER_SLUG)
        user_id = await self._get_superuser_id(auth_manager)

        for slug in (self._APP_SLUG, self._ANOTHER_SLUG):
            await client.post(
                "/api/auth/admin/apps/register",
                headers={"Authorization": f"Bearer {superuser_token}"},
                json={"user_id": user_id, "app_slug": slug},
            )

        resp = await client.get(
            f"/api/auth/admin/apps/users/{user_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert self._APP_SLUG in data["app_slugs"]
        assert self._ANOTHER_SLUG in data["app_slugs"]

    async def test_unregister_user_from_app(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """POST /api/auth/admin/apps/unregister should remove user from app."""
        await self._create_app(auth_manager, self._APP_SLUG)
        user_id = await self._get_superuser_id(auth_manager)

        await client.post(
            "/api/auth/admin/apps/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": self._APP_SLUG},
        )

        resp = await client.post(
            "/api/auth/admin/apps/unregister",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": self._APP_SLUG},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["unregistered"] is True

        get_resp = await client.get(
            f"/api/auth/admin/apps/users/{user_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert self._APP_SLUG not in get_resp.json()["app_slugs"]

    async def test_unregister_non_registered_user(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """POST /api/auth/admin/apps/unregister when user is not registered should return 404."""
        await self._create_app(auth_manager, self._APP_SLUG)
        user_id = await self._get_superuser_id(auth_manager)
        resp = await client.post(
            "/api/auth/admin/apps/unregister",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": self._APP_SLUG},
        )
        assert resp.status_code == 404

    async def test_requires_superuser(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """App membership endpoints should return 403 for non-superusers."""
        from dhanada.auth.db.repository import RefreshTokenRepository, UserRepository
        from dhanada.auth.db.session import DatabaseSession
        from dhanada.auth.services.token_service import TokenService

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            token_repo = RefreshTokenRepository(session)
            token_service = TokenService(token_repo, user_repo, auth_manager._jwt)

            password_hash = auth_manager._password_manager.hash_password("TestPass123!")
            user = await user_repo.create(
                email="regular-app@test.com",
                username="regularapp",
                password_hash=password_hash,
                full_name="Regular User",
                is_active=True,
                is_superuser=False,
            )
            await session.commit()
            result = await token_service.create_tokens(user_id=user.id)
            token = result.access_token

        resp = await client.post(
            "/api/auth/admin/apps/register",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": str(user.id), "app_slug": "some-app"},
        )
        assert resp.status_code == 403

    async def test_register_duplicate(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """Registering a user twice to the same app should return 200 (idempotent)."""
        await self._create_app(auth_manager, self._APP_SLUG)
        user_id = await self._get_superuser_id(auth_manager)

        resp1 = await client.post(
            "/api/auth/admin/apps/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": self._APP_SLUG},
        )
        assert resp1.status_code == 200

        resp2 = await client.post(
            "/api/auth/admin/apps/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"user_id": user_id, "app_slug": self._APP_SLUG},
        )
        assert resp2.status_code == 200
