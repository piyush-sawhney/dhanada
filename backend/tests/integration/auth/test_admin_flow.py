"""Integration tests for admin user management flows."""

import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestAdminUserCRUD:
    """Tests for admin user CRUD operations."""

    TEST_EMAIL = "admin-crud@test.com"
    TEST_USERNAME = "admin-crud"
    TEST_FULL_NAME = "Admin CRUD User"

    async def test_register_user(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /register should create an inactive user with temp password."""
        resp = await client.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={
                "email": self.TEST_EMAIL,
                "username": self.TEST_USERNAME,
                "full_name": self.TEST_FULL_NAME,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == self.TEST_EMAIL
        assert data["is_active"] is False
        assert "temporary_password" in data

    async def test_register_user_with_role(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """POST /register with role_name should assign the role."""
        from dhanada.auth.db.repository import RoleRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            role_repo = RoleRepository(session)
            role = await role_repo.get_by_name("admin")
            if role is None:
                role = await role_repo.create(  # noqa: E501
                    name="admin", description="Test admin", is_system=False,
                )
                await session.commit()

        resp = await client.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={
                "email": "role-register@test.com",
                "username": "roleregister",
                "full_name": "Role Register",
                "role_name": "admin",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "admin" in data["roles"]

    async def test_list_users(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /users should return paginated user list."""
        resp = await client.get(
            "/api/auth/users",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1

    async def test_list_users_with_search(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /users with search param should filter results."""
        resp = await client.get(
            f"/api/auth/users?search={self.TEST_USERNAME}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        emails = [u["email"] for u in data["users"]]
        assert self.TEST_EMAIL in emails

    async def test_get_user_by_id(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """GET /users/{user_id} should return user details."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email(self.TEST_EMAIL)

        resp = await client.get(
            f"/api/auth/users/{user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == self.TEST_EMAIL
        assert data["username"] == self.TEST_USERNAME

    async def test_admin_update_user(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """PATCH /users/{user_id} should update user fields."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email(self.TEST_EMAIL)

        resp = await client.patch(
            f"/api/auth/users/{user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"full_name": "Updated Name", "is_active": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Updated Name"
        assert data["is_active"] is True

    async def test_admin_reset_user_auth(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """POST /admin/users/{user_id}/reset-auth should reset user auth."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email(self.TEST_EMAIL)

        resp = await client.post(
            f"/api/auth/admin/users/{user.id}/reset-auth",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "temporary_password" in data

    async def test_delete_user(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """DELETE /users/{user_id} should soft-delete a user."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email(self.TEST_EMAIL)

        resp = await client.delete(
            f"/api/auth/users/{user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
