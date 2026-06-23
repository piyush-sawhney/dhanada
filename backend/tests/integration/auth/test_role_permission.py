"""Integration tests for role and permission management."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _role_name():
    """Generate a unique role name per call."""
    import uuid
    return f"test-role-int-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def created_role(client: AsyncClient, superuser_token: str):
    """Create a role for testing and return its name and id."""
    name = _role_name()
    resp = await client.post(
        "/api/auth/roles/create",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": name, "description": "Integration test role"},
    )
    assert resp.status_code == 201
    return {"name": name, "id": resp.json()["id"]}


class TestRoleCRUD:
    """Tests for role CRUD operations."""

    async def test_create_role(self, client: AsyncClient, superuser_token: str):
        """POST /roles/create should create a new role."""
        name = _role_name()
        resp = await client.post(
            "/api/auth/roles/create",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"name": name, "description": "Integration test role"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["description"] == "Integration test role"
        assert data["is_system"] is False

    async def test_create_duplicate_role(
        self, client: AsyncClient, superuser_token: str, created_role: dict
    ):
        """POST /roles/create with duplicate name should return 409."""
        resp = await client.post(
            "/api/auth/roles/create",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"name": created_role["name"], "description": "Integration test role"},
        )
        assert resp.status_code == 409

    async def test_get_role_by_name(
        self, client: AsyncClient, superuser_token: str, created_role: dict
    ):
        """GET /roles/{role_name} should return the role with permissions."""
        resp = await client.get(
            f"/api/auth/roles/{created_role['name']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == created_role["name"]
        assert "permissions" in data

    async def test_get_nonexistent_role(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /roles/{role_name} with non-existent role should return 404."""
        resp = await client.get(
            "/api/auth/roles/nonexistent-role",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_list_roles(self, client: AsyncClient, superuser_token: str, created_role: dict):
        """GET /roles/all should list all roles."""
        resp = await client.get(
            "/api/auth/roles/all",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data
        role_names = [r["name"] for r in data["roles"]]
        assert created_role["name"] in role_names

    async def test_add_permission_to_role(
        self, client: AsyncClient, superuser_token: str, created_role: dict
    ):
        """POST /roles/{role_name}/permissions should add a permission."""
        resp = await client.post(
            f"/api/auth/roles/{created_role['name']}/permissions",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"resource": "test-resource", "action": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["added"] is True

    async def test_remove_permission_from_role(
        self, client: AsyncClient, superuser_token: str, created_role: dict
    ):
        """DELETE /roles/{role_name}/permissions should remove a permission."""
        # First add the permission
        add_resp = await client.post(
            f"/api/auth/roles/{created_role['name']}/permissions",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"resource": "test-resource", "action": "read"},
        )
        assert add_resp.status_code == 200

        resp = await client.request(
            "DELETE",
            f"/api/auth/roles/{created_role['name']}/permissions",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"resource": "test-resource", "action": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["removed"] is True

    async def test_remove_nonexistent_permission(
        self, client: AsyncClient, superuser_token: str, created_role: dict
    ):
        """DELETE /roles/{role_name}/permissions with non-existent perm should return 404."""
        resp = await client.request(
            "DELETE",
            f"/api/auth/roles/{created_role['name']}/permissions",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"resource": "nonexistent", "action": "read"},
        )
        assert resp.status_code == 404

    async def test_assign_role_to_user(
        self, client: AsyncClient, superuser_token: str, auth_manager, created_role: dict
    ):
        """POST /roles should assign a role to a user."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        resp = await client.post(
            f"/api/auth/roles?user_id={user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"role_name": created_role["name"]},
        )
        assert resp.status_code == 200
        assert resp.json()["assigned"] is True

    async def test_get_user_roles(
        self, client: AsyncClient, superuser_token: str, auth_manager, created_role: dict
    ):
        """GET /roles should return user's roles."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        # First assign the role
        assign_resp = await client.post(
            f"/api/auth/roles?user_id={user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"role_name": created_role["name"]},
        )
        assert assign_resp.status_code == 200

        resp = await client.get(
            f"/api/auth/roles?user_id={user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        roles = resp.json()
        assert created_role["name"] in roles

    async def test_revoke_role_from_user(
        self, client: AsyncClient, superuser_token: str, auth_manager, created_role: dict
    ):
        """DELETE /roles should revoke a role from a user."""
        from dhanada.auth.db.repository import UserRepository
        from dhanada.auth.db.session import DatabaseSession

        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_email("super@test.com")

        # First assign the role
        assign_resp = await client.post(
            f"/api/auth/roles?user_id={user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"role_name": created_role["name"]},
        )
        assert assign_resp.status_code == 200

        resp = await client.request(
            "DELETE",
            f"/api/auth/roles?user_id={user.id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"role_name": created_role["name"]},
        )
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True

    async def test_delete_role(self, client: AsyncClient, superuser_token: str, created_role: dict):
        """DELETE /roles/{role_id} should delete a role."""
        resp = await client.delete(
            f"/api/auth/roles/{created_role['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestPermissionCheck:
    """Tests for permission checking."""

    async def test_check_permission(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /permissions/check should return permission status."""
        resp = await client.get(
            "/api/auth/permissions/check?resource=users&action=read",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "allowed" in data
        assert data["resource"] == "users"
        assert data["action"] == "read"

    async def test_get_my_permissions(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /permissions should return current user's permissions."""
        resp = await client.get(
            "/api/auth/permissions",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        permissions = resp.json()
        assert isinstance(permissions, list)
