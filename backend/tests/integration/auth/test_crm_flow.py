"""Integration tests for CRM (client and document) endpoints."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestClientCRUD:
    """Tests for client CRUD operations.

    Each test creates its own unique PAN to remain independent —
    there is no ``_clean_tables`` between functions in integration tests.
    """

    _CLIENT_NAME = "Test Client"
    _UPDATED_NAME = "Updated Client"

    async def _create_client(
        self, client: AsyncClient, token: str, name: str, pan: str
    ) -> dict:
        resp = await client.post(
            "/api/crm/clients",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": name, "pan": pan},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_create_client(self, client: AsyncClient, superuser_token: str):
        """POST /api/crm/clients should create a new client."""
        data = await self._create_client(client, superuser_token, self._CLIENT_NAME, "ABCDE1234F")
        assert data["name"] == self._CLIENT_NAME
        assert data["pan_number_hash"] is not None
        assert data["is_active"] is True
        assert "id" in data
        assert "pan" not in data  # never returned without manage-pan

    async def test_create_client_duplicate_pan(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/clients with same PAN should return 400."""
        await self._create_client(client, superuser_token, name="First", pan="AAAAA1111A")
        resp = await client.post(
            "/api/crm/clients",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"name": "Second", "pan": "AAAAA1111A"},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    async def test_create_client_invalid_pan(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/clients with invalid PAN should return 422."""
        resp = await client.post(
            "/api/crm/clients",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"name": "Bad PAN Client", "pan": "invalid"},
        )
        assert resp.status_code == 422

    async def test_list_clients(self, client: AsyncClient, superuser_token: str):
        """GET /api/crm/clients should return paginated list."""
        await self._create_client(client, superuser_token, "List Test", "LSTCL1234F")
        resp = await client.get(
            "/api/crm/clients",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["items"][0]["name"] == "List Test"

    async def test_list_clients_with_search(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /api/crm/clients?search= should filter by name."""
        await self._create_client(client, superuser_token, "Alice", "ALICL1234F")
        await self._create_client(client, superuser_token, "Bob", "ZZZZZ9999Z")
        resp = await client.get(
            "/api/crm/clients?search=Alice",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [i["name"] for i in data["items"]]
        assert "Alice" in names
        assert "Bob" not in names

    async def test_get_client(self, client: AsyncClient, superuser_token: str):
        """GET /api/crm/clients/{id} should return the client."""
        created = await self._create_client(client, superuser_token, "Get Test", "GETCL1234F")
        resp = await client.get(
            f"/api/crm/clients/{created['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    async def test_get_client_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /api/crm/clients/{id} with non-existent ID should return 404."""
        resp = await client.get(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_update_client(self, client: AsyncClient, superuser_token: str):
        """PATCH /api/crm/clients/{id} should update the client name."""
        created = await self._create_client(client, superuser_token, "Update Test", "UPCLT1234F")
        resp = await client.patch(
            f"/api/crm/clients/{created['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"name": self._UPDATED_NAME},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == self._UPDATED_NAME

    async def test_soft_delete_client(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/clients/{id} should soft-delete the client."""
        created = await self._create_client(client, superuser_token, "Soft Del", "SDCLT1234F")
        resp = await client.delete(
            f"/api/crm/clients/{created['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 204

        get_resp = await client.get(
            f"/api/crm/clients/{created['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert get_resp.status_code == 404

    async def test_restore_client(self, client: AsyncClient, superuser_token: str):
        """POST /api/crm/clients/{id}/restore should restore soft-deleted client."""
        created = await self._create_client(client, superuser_token, "Restore", "RSVCL1234F")
        await client.delete(
            f"/api/crm/clients/{created['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        resp = await client.post(
            f"/api/crm/clients/{created['id']}/restore",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True
        assert resp.json()["id"] == created["id"]

    async def test_hard_delete_client(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/clients/{id}/hard should permanently delete."""
        created = await self._create_client(client, superuser_token, "Hard Del", "HDCLT1234F")
        await client.delete(
            f"/api/crm/clients/{created['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        resp = await client.delete(
            f"/api/crm/clients/{created['id']}/hard",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 204

    async def test_get_client_pan(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """GET /api/crm/clients/{id}/pan should return decrypted PAN."""
        await _ensure_permission(auth_manager, superuser_token, "clients:manage-pan")
        created = await self._create_client(client, superuser_token, "Get PAN", "GPANC1234L")
        resp = await client.get(
            f"/api/crm/clients/{created['id']}/pan",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pan"] == "GPANC1234L"

    async def test_update_client_pan(
        self, client: AsyncClient, superuser_token: str, auth_manager: AuthManager
    ):
        """PATCH /api/crm/clients/{id}/pan should update the PAN."""
        await _ensure_permission(auth_manager, superuser_token, "clients:manage-pan")
        created = await self._create_client(client, superuser_token, "Upd PAN", "UPNCL1234X")
        new_pan = "UPNCL5678Y"
        resp = await client.patch(
            f"/api/crm/clients/{created['id']}/pan",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"pan": new_pan},
        )
        assert resp.status_code == 200

        get_resp = await client.get(
            f"/api/crm/clients/{created['id']}/pan",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert get_resp.json()["pan"] == new_pan

    async def test_export_csv(self, client: AsyncClient, superuser_token: str):
        """POST /api/crm/clients/export should return CSV."""
        await self._create_client(client, superuser_token, name="Export1", pan="FGHIJ5678K")
        await self._create_client(client, superuser_token, name="Export2", pan="LMNOP9012Q")
        resp = await client.post(
            "/api/crm/clients/export",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        body = resp.text
        assert "name" in body
        assert "Export1" in body
        assert "Export2" in body

    async def test_create_client_no_permission(
        self, client: AsyncClient, auth_manager: AuthManager
    ):
        """POST /api/crm/clients without clients:create should return 403."""
        token = await _make_user_token(auth_manager, "no-perm@test.com", ["documents:read"])
        resp = await client.post(
            "/api/crm/clients",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "No Perm Client", "pan": "HIJKL3456M"},
        )
        assert resp.status_code == 403

    async def test_unauthorized_access(
        self, client: AsyncClient
    ):
        """Any CRM endpoint without a token should return 401."""
        resp = await client.post(
            "/api/crm/clients",
            json={"name": "No Auth", "pan": "NOPQR7890S"},
        )
        assert resp.status_code == 401


class TestDocumentCRUD:
    """Tests for document CRUD operations.

    Each test creates its own client with a unique PAN to remain independent.
    """

    async def _create_client(self, client: AsyncClient, token: str, pan: str) -> dict:
        resp = await client.post(
            "/api/crm/clients",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Doc Test Client", "pan": pan},
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_create_id_document(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/documents should create an ID document with photo."""
        cl = await self._create_client(client, superuser_token, "DOCID1234A")
        photo_bytes = b"fake-jpeg-data"
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.jpg", io.BytesIO(photo_bytes), "image/jpeg"),
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["client_id"] == cl["id"]
        assert data["has_front_photo"] is True
        assert data["has_back_photo"] is False

    async def test_create_non_id_document(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/documents should create a non-ID document with file."""
        cl = await self._create_client(client, superuser_token, "DOCNI1234B")
        file_bytes = b"fake-file-content"
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "invoice",
                "is_id": "false",
                "issue_date": "2024-03-20",
            },
            files={
                "file": ("invoice.pdf", io.BytesIO(file_bytes), "application/pdf"),
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["has_front_photo"] is False
        assert data["has_back_photo"] is False

    async def test_list_documents(self, client: AsyncClient, superuser_token: str):
        """GET /api/crm/documents should return paginated list."""
        cl = await self._create_client(client, superuser_token, "DOCLS1234C")
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "aadhaar",
                "is_id": "true",
                "issue_date": "2024-06-01",
            },
            files={"front_photo": ("front.jpg", io.BytesIO(b"data"), "image/jpeg")},
        )
        assert resp.status_code == 201

        list_resp = await client.get(
            f"/api/crm/documents?client_id={cl['id']}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["client_id"] == cl["id"]

    async def test_get_document_front_photo(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /api/crm/documents/{id}/photo/front should stream photo."""
        cl = await self._create_client(client, superuser_token, "DOCPH1234D")
        photo_bytes = b"fake-jpeg-data-123"
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.jpg", io.BytesIO(photo_bytes), "image/jpeg"),
            },
        )
        doc_id = doc_resp.json()["id"]

        photo_resp = await client.get(
            f"/api/crm/documents/{doc_id}/photo/front",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert photo_resp.status_code == 200
        assert photo_resp.content == photo_bytes

    async def test_update_document(
        self, client: AsyncClient, superuser_token: str
    ):
        """PATCH /api/crm/documents/{id} should update metadata."""
        cl = await self._create_client(client, superuser_token, "DOCUP1234E")
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={"front_photo": ("front.jpg", io.BytesIO(b"data"), "image/jpeg")},
        )
        doc_id = doc_resp.json()["id"]

        upd_resp = await client.patch(
            f"/api/crm/documents/{doc_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"document_type": "visa"},
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["document_type"] == "visa"

    async def test_soft_delete_document(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/documents/{id} should soft-delete."""
        cl = await self._create_client(client, superuser_token, "DOCSD1234F")
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={"front_photo": ("front.jpg", io.BytesIO(b"data"), "image/jpeg")},
        )
        doc_id = doc_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/crm/documents/{doc_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert del_resp.status_code == 204

        get_resp = await client.get(
            f"/api/crm/documents/{doc_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert get_resp.status_code == 404

    async def test_restore_document(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/documents/{id}/restore should restore."""
        cl = await self._create_client(client, superuser_token, "DOCRS1234G")
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={"front_photo": ("front.jpg", io.BytesIO(b"data"), "image/jpeg")},
        )
        doc_id = doc_resp.json()["id"]

        await client.delete(
            f"/api/crm/documents/{doc_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        rest_resp = await client.post(
            f"/api/crm/documents/{doc_id}/restore",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert rest_resp.status_code == 200
        assert rest_resp.json()["id"] == doc_id

    async def test_document_photo_too_large(
        self, client: AsyncClient, superuser_token: str
    ):
        """Creating a document with >2MB photo should return 400."""
        cl = await self._create_client(client, superuser_token, "DOCPL1234H")
        large_photo = b"x" * (2 * 1024 * 1024 + 1)
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.jpg", io.BytesIO(large_photo), "image/jpeg"),
            },
        )
        assert resp.status_code == 400

    async def test_document_wrong_front_mime(
        self, client: AsyncClient, superuser_token: str
    ):
        """Creating a document with non-JPEG/PNG front photo should return 400."""
        cl = await self._create_client(client, superuser_token, "DOCFM1234I")
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.gif", io.BytesIO(b"gif-data"), "image/gif"),
            },
        )
        assert resp.status_code == 400

    async def test_document_back_photo_too_large(
        self, client: AsyncClient, superuser_token: str
    ):
        """Creating a document with >2MB back photo should return 400."""
        cl = await self._create_client(client, superuser_token, "DOCBL1234J")
        large_photo = b"y" * (2 * 1024 * 1024 + 1)
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.jpg", io.BytesIO(b"valid"), "image/jpeg"),
                "back_photo": ("back.jpg", io.BytesIO(large_photo), "image/jpeg"),
            },
        )
        assert resp.status_code == 400

    async def test_document_wrong_back_mime(
        self, client: AsyncClient, superuser_token: str
    ):
        """Creating a document with non-JPEG/PNG back photo should return 400."""
        cl = await self._create_client(client, superuser_token, "DOCBM1234K")
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.jpg", io.BytesIO(b"valid"), "image/jpeg"),
                "back_photo": ("back.gif", io.BytesIO(b"gif-data"), "image/gif"),
            },
        )
        assert resp.status_code == 400

    async def test_create_non_id_document_without_file(
        self, client: AsyncClient, superuser_token: str
    ):
        """Creating a non-ID document without a file should still succeed (no file)."""
        cl = await self._create_client(client, superuser_token, "DOCNF1234L")
        resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "invoice",
                "is_id": "false",
                "issue_date": "2024-05-10",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["has_front_photo"] is False
        assert data["has_back_photo"] is False

    async def test_get_document_front_photo_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /photo/front on an ID doc without front photo should return 404."""
        cl = await self._create_client(client, superuser_token, "DOCFN1234M")
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
        )
        doc_id = doc_resp.json()["id"]
        resp = await client.get(
            f"/api/crm/documents/{doc_id}/photo/front",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_get_document_back_photo(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /api/crm/documents/{id}/photo/back should stream photo."""
        cl = await self._create_client(client, superuser_token, "DOCBP1234N")
        photo_bytes = b"fake-back-jpeg"
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={
                "front_photo": ("front.jpg", io.BytesIO(b"front"), "image/jpeg"),
                "back_photo": ("back.jpg", io.BytesIO(photo_bytes), "image/jpeg"),
            },
        )
        doc_id = doc_resp.json()["id"]
        photo_resp = await client.get(
            f"/api/crm/documents/{doc_id}/photo/back",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert photo_resp.status_code == 200
        assert photo_resp.content == photo_bytes

    async def test_get_document_back_photo_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /photo/back on an ID doc without back photo should return 404."""
        cl = await self._create_client(client, superuser_token, "DOCBN1234O")
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={"front_photo": ("front.jpg", io.BytesIO(b"front"), "image/jpeg")},
        )
        doc_id = doc_resp.json()["id"]
        resp = await client.get(
            f"/api/crm/documents/{doc_id}/photo/back",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_hard_delete_document(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/documents/{id}/hard should permanently delete."""
        cl = await self._create_client(client, superuser_token, "DOCHD1234P")
        doc_resp = await client.post(
            "/api/crm/documents",
            headers={"Authorization": f"Bearer {superuser_token}"},
            data={
                "client_id": cl["id"],
                "document_type": "passport",
                "is_id": "true",
                "issue_date": "2024-01-15",
            },
            files={"front_photo": ("front.jpg", io.BytesIO(b"data"), "image/jpeg")},
        )
        doc_id = doc_resp.json()["id"]
        await client.delete(
            f"/api/crm/documents/{doc_id}",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        hard_resp = await client.delete(
            f"/api/crm/documents/{doc_id}/hard",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert hard_resp.status_code == 204

    async def test_update_client_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """PATCH /api/crm/clients/{id} with non-existent ID should return 404."""
        resp = await client.patch(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    async def test_soft_delete_client_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/clients/{id} with non-existent ID should return 404."""
        resp = await client.delete(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_hard_delete_client_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/clients/{id}/hard with non-existent ID should return 404."""
        resp = await client.delete(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000/hard",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_restore_client_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/clients/{id}/restore with non-existent ID should return 404."""
        resp = await client.post(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000/restore",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_get_client_pan_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """GET /api/crm/clients/{id}/pan with non-existent ID should return 404."""
        resp = await client.get(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000/pan",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_update_client_pan_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """PATCH /api/crm/clients/{id}/pan with non-existent ID should return 404."""
        resp = await client.patch(
            "/api/crm/clients/00000000-0000-0000-0000-000000000000/pan",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"pan": "ABCDE1234F"},
        )
        assert resp.status_code == 404

    async def test_soft_delete_document_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/documents/{id} with non-existent ID should return 404."""
        resp = await client.delete(
            "/api/crm/documents/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_restore_document_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /api/crm/documents/{id}/restore with non-existent ID should return 404."""
        resp = await client.post(
            "/api/crm/documents/00000000-0000-0000-0000-000000000000/restore",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404

    async def test_hard_delete_document_not_found(
        self, client: AsyncClient, superuser_token: str
    ):
        """DELETE /api/crm/documents/{id}/hard with non-existent ID should return 404."""
        resp = await client.delete(
            "/api/crm/documents/00000000-0000-0000-0000-000000000000/hard",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 404


async def _ensure_permission(
    auth_manager: AuthManager,  # noqa: ARG001
    user_token: str,  # noqa: ARG001
    permission_slug: str,  # noqa: ARG001
) -> None:
    """Ensure the superuser has a specific permission via a role.

    Superusers bypass permission checks — this is a no-op.
    The fixture exists for extensibility when testing non-superuser roles.
    """


async def _make_user_token(
    auth_manager: AuthManager, email: str, permission_slugs: list[str]
) -> str:
    """Create a non-superuser user with specific permissions and return a token."""
    from dhanada.auth.db.repository import RefreshTokenRepository, RoleRepository, UserRepository
    from dhanada.auth.db.session import DatabaseSession
    from dhanada.auth.services.token_service import TokenService

    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        user_repo = UserRepository(session)
        token_repo = RefreshTokenRepository(session)
        role_repo = RoleRepository(session)
        token_service = TokenService(token_repo, user_repo, auth_manager._jwt)

        password_hash = auth_manager._password_manager.hash_password("TestPass123!")
        user = await user_repo.create(
            email=email,
            username=email.split("@")[0],
            password_hash=password_hash,
            full_name="Permission Test",
            is_active=True,
            is_superuser=False,
        )

        role = await role_repo.create(
            name=f"role_{email.split('@')[0]}",
            description="Test role for permissions",
            is_system=False,
        )
        for slug in permission_slugs:
            resource, action = slug.split(":", 1)
            await role_repo.add_permission(role.id, resource, action)
        await session.flush()

        await role_repo.assign_role_to_user(user.id, role.id, created_by_id=user.id)
        result = await token_service.create_tokens(user_id=user.id)
        await session.commit()
        return result.access_token
