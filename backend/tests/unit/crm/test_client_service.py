"""Tests for ClientService."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from dhanada.auth.exceptions import UserNotFoundError


class TestClientService:
    async def test_create_client(self, client_service, test_user):
        """Creating a client should return a Client with encrypted PAN."""
        client = await client_service.create(
            user_id=test_user.id,
            name="Acme Corp",
            pan="ABCDE1234A",
        )
        assert client.name == "Acme Corp"
        assert client.pan_number_hash != "ABCDE1234A"  # Hashed
        assert client.encrypted_pan is not None  # Encrypted
        assert client.is_active is True
        assert client.created_by_id == test_user.id

    async def test_create_client_lowercase_pan(self, client_service, test_user):
        """PAN should be normalized to uppercase on creation."""
        client = await client_service.create(
            user_id=test_user.id,
            name="Test",
            pan="abcde1234a",
        )
        pan = await client_service.get_pan(test_user.id, client.id)
        assert pan == "ABCDE1234A"

    async def test_create_duplicate_pan_raises(self, client_service, test_user):
        """Creating two clients with same PAN should raise."""
        await client_service.create(
            user_id=test_user.id,
            name="One",
            pan="ABCDE1234A",
        )
        with pytest.raises(IntegrityError):
            await client_service.create(
                user_id=test_user.id,
                name="Two",
                pan="ABCDE1234A",
            )

    async def test_get_client(self, client_service, test_user):
        """Getting a client should return the correct client."""
        created = await client_service.create(
            user_id=test_user.id,
            name="Acme Corp",
            pan="ABCDE1234A",
        )
        retrieved = await client_service.get(test_user.id, created.id)
        assert retrieved.id == created.id
        assert retrieved.name == "Acme Corp"

    async def test_get_nonexistent_raises(self, client_service, test_user):
        """Getting a non-existent client should raise."""
        with pytest.raises(UserNotFoundError):
            await client_service.get(test_user.id, uuid.uuid4())

    async def test_get_soft_deleted_raises(self, client_service, test_user):
        """Getting a soft-deleted client should raise."""
        client = await client_service.create(
            user_id=test_user.id,
            name="Del Corp",
            pan="FGHIJ5678F",
        )
        await client_service.soft_delete(test_user.id, client.id)
        with pytest.raises(UserNotFoundError):
            await client_service.get(test_user.id, client.id)

    async def test_list_clients(self, client_service, test_user):
        """Listing should return all active clients."""
        await client_service.create(
            user_id=test_user.id,
            name="Alpha",
            pan="AAAAA1111A",
        )
        await client_service.create(
            user_id=test_user.id,
            name="Beta",
            pan="BBBBB2222B",
        )
        clients, total = await client_service.list_all(test_user.id)
        assert total >= 2
        assert len(clients) >= 2

    async def test_list_search(self, client_service, test_user):
        """Search should filter by name."""
        await client_service.create(
            user_id=test_user.id,
            name="UniqueName",
            pan="CCCCC3333C",
        )
        results, total = await client_service.list_all(test_user.id, search="Unique")
        assert total == 1
        assert len(results) == 1
        assert results[0].name == "UniqueName"

    async def test_soft_delete(self, client_service, test_user):
        """Soft delete should mark as inactive with deleted_at."""
        client = await client_service.create(
            user_id=test_user.id,
            name="Del Corp",
            pan="DDDDD4444D",
        )
        result = await client_service.soft_delete(test_user.id, client.id)
        assert result is True

    async def test_get_pan(self, client_service, test_user):
        """Getting PAN should return the decrypted PAN."""
        client = await client_service.create(
            user_id=test_user.id,
            name="Pan Test",
            pan="EEEEE5555E",
        )
        pan = await client_service.get_pan(test_user.id, client.id)
        assert pan == "EEEEE5555E"

    async def test_update_pan(self, client_service, test_user):
        """Updating PAN should change the stored encrypted PAN."""
        client = await client_service.create(
            user_id=test_user.id,
            name="Pan Update",
            pan="FFFFF6666F",
        )
        await client_service.update_pan(
            test_user.id,
            client.id,
            pan="GGGGG7777G",
        )
        pan = await client_service.get_pan(test_user.id, client.id)
        assert pan == "GGGGG7777G"

    async def test_export_csv(self, client_service, test_user):
        """Export CSV should return valid CSV string."""
        await client_service.create(
            user_id=test_user.id,
            name="CSV Corp",
            pan="HHHHH8888H",
        )
        csv_content = await client_service.export_csv(test_user.id)
        assert "name" in csv_content
        assert "CSV Corp" in csv_content

    async def test_export_csv_includes_pan_when_permitted(self, client_service, test_user):
        """Export CSV includes PAN column when user has manage-pan permission."""
        await client_service.create(
            user_id=test_user.id,
            name="Pan Export",
            pan="IIIII9999I",
        )
        csv_content = await client_service.export_csv(test_user.id)
        assert "pan" in csv_content
        assert "IIIII9999I" in csv_content

    async def test_list_pagination(self, client_service, test_user):
        """List should respect offset and limit."""
        for i in range(10):
            pan = f"AAAAA{i:04d}A"
            await client_service.create(
                user_id=test_user.id,
                name=f"Client {i}",
                pan=pan,
            )
        page1, total = await client_service.list_all(test_user.id, offset=0, limit=3)
        assert total == 10
        assert len(page1) == 3

        page2, total = await client_service.list_all(test_user.id, offset=3, limit=3)
        assert len(page2) == 3
        assert page2[0].id != page1[0].id

    async def test_list_with_status_all(self, client_service, test_user):
        """List with include_inactive=True shows soft-deleted clients."""
        client = await client_service.create(
            user_id=test_user.id,
            name="To Delete",
            pan="JJJJJ0000J",
        )
        await client_service.soft_delete(test_user.id, client.id)
        active, total_active = await client_service.list_all(test_user.id, include_inactive=False)
        assert client.id not in [c.id for c in active]

        all_clients, total_all = await client_service.list_all(test_user.id, include_inactive=True)
        assert client.id in [c.id for c in all_clients]
