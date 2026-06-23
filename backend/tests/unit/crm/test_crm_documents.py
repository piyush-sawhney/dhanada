"""Tests for DocumentService."""

import uuid
from datetime import date
from pathlib import Path

import aiofiles
import aiofiles.os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.exceptions import UserNotFoundError
from dhanada.crm.services import ClientService, DocumentService
from dhanada.crm.storage import LocalFileStorage, StorageBackend


@pytest_asyncio.fixture
async def shared_session(auth_manager) -> AsyncSession:
    """Create a DB session shared across services to avoid FK isolation issues."""
    db = DatabaseSession(str(auth_manager.config.database_url))
    async with db.session() as session:
        yield session
        await session.flush()


@pytest_asyncio.fixture
async def svc_client(auth_manager, shared_session) -> ClientService:
    return ClientService(
        session=shared_session,
        auth=auth_manager,
        envelope=auth_manager._envelope,
    )


@pytest_asyncio.fixture
async def svc_doc(auth_manager, shared_session) -> DocumentService:
    return DocumentService(
        session=shared_session,
        auth=auth_manager,
        envelope=auth_manager._envelope,
    )


@pytest_asyncio.fixture
async def svc_doc_with_storage(
    auth_manager, shared_session, tmp_path: Path,
) -> DocumentService:
    storage: StorageBackend = LocalFileStorage(str(tmp_path))
    return DocumentService(
        session=shared_session,
        auth=auth_manager,
        envelope=auth_manager._envelope,
        storage=storage,
    )


class TestDocumentService:
    async def _create_client(self, svc_client, test_user, name="Doc Test Client"):
        return await svc_client.create(
            user_id=test_user.id,
            name=name,
            pan="ABCDE1234A",
        )

    async def test_create_minimal(self, svc_doc, svc_client, test_user):
        """Create document with only required fields, no photos."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        assert doc.id is not None
        assert doc.document_type == "pan_card"
        assert doc.document_number is None
        assert doc.is_id is True
        assert doc.front_photo_data is None
        assert doc.back_photo_data is None
        assert doc.is_active is True
        assert doc.created_by_id == test_user.id

    async def test_create_full(self, svc_doc, svc_client, test_user):
        """Create document with all fields including encrypted photos."""
        client = await self._create_client(svc_client, test_user)
        front_bytes = b"fake_jpeg_bytes_front"
        back_bytes = b"fake_jpeg_bytes_back"
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="passport",
            document_number="PP123456",
            issue_date=date(2024, 1, 1),
            expiry_date=date(2029, 1, 1),
            front_photo=front_bytes,
            front_photo_mime="image/jpeg",
            back_photo=back_bytes,
            back_photo_mime="image/png",
        )
        assert doc.document_number == "PP123456"
        assert doc.front_photo_data is not None
        assert doc.front_photo_mime == "image/jpeg"
        assert doc.back_photo_data is not None
        assert doc.back_photo_mime == "image/png"

    async def test_create_other_type(self, svc_doc, svc_client, test_user):
        """Create document with 'other' type and custom description."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="other",
            document_type_other="Property Deed",
            issue_date=date(2024, 6, 1),
        )
        assert doc.document_type == "other"
        assert doc.document_type_other == "Property Deed"

    async def test_create_other_type_missing_desc_raises(self, svc_doc, svc_client, test_user):
        """Creating with type 'other' but no description should raise."""
        client = await self._create_client(svc_client, test_user)
        with pytest.raises(ValueError, match="document_type_other is required"):
            await svc_doc.create(
                user_id=test_user.id,
                client_id=client.id,
                document_type="other",
                issue_date=date(2024, 6, 1),
            )

    async def test_create_duplicate_number_raises(self, svc_doc, svc_client, test_user):
        """Duplicate document number should raise ValueError."""
        client = await self._create_client(svc_client, test_user)
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            document_number="UNIQUE001",
            issue_date=date(2024, 1, 1),
        )
        with pytest.raises(ValueError, match="already exists"):
            await svc_doc.create(
                user_id=test_user.id,
                client_id=client.id,
                document_type="aadhaar",
                document_number="UNIQUE001",
                issue_date=date(2024, 1, 1),
            )

    async def test_get_document(self, svc_doc, svc_client, test_user):
        """Getting a document returns the correct document."""
        client = await self._create_client(svc_client, test_user)
        created = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        retrieved = await svc_doc.get(test_user.id, created.id)
        assert retrieved.id == created.id
        assert retrieved.client_id == client.id

    async def test_get_nonexistent_raises(self, svc_doc, test_user):
        """Getting a non-existent document should raise."""
        with pytest.raises(UserNotFoundError):
            await svc_doc.get(test_user.id, uuid.uuid4())

    async def test_list_documents(self, svc_doc, svc_client, test_user):
        """Listing returns all active documents."""
        client = await self._create_client(svc_client, test_user)
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="aadhaar",
            issue_date=date(2024, 2, 1),
        )
        docs, total = await svc_doc.list_all(test_user.id)
        assert total >= 2
        assert len(docs) >= 2

    async def test_list_filter_by_client(self, svc_doc, svc_client, test_user):
        """List can filter by client_id."""
        client1 = await self._create_client(svc_client, test_user, name="Client A")
        client2 = await self._create_client(svc_client, test_user, name="Client B")
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client1.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client2.id,
            document_type="aadhaar",
            issue_date=date(2024, 2, 1),
        )
        docs, total = await svc_doc.list_all(test_user.id, client_id=client1.id)
        assert total == 1
        assert len(docs) == 1
        assert docs[0].client_id == client1.id

    async def test_list_filter_by_type(self, svc_doc, svc_client, test_user):
        """List can filter by document_type."""
        client = await self._create_client(svc_client, test_user)
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="passport",
            issue_date=date(2024, 2, 1),
        )
        docs, total = await svc_doc.list_all(test_user.id, document_type="passport")
        assert total == 1
        assert len(docs) == 1
        assert docs[0].document_type == "passport"

    async def test_front_photo_roundtrip(self, svc_doc, svc_client, test_user):
        """Decrypted front photo matches original bytes."""
        original = b"fake_jpeg_bytes_front_photo_data"
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
            front_photo=original,
            front_photo_mime="image/jpeg",
        )
        result = await svc_doc.get_front_photo(test_user.id, doc.id)
        assert result is not None
        photo_bytes, mime = result
        assert photo_bytes == original
        assert mime == "image/jpeg"

    async def test_back_photo_roundtrip(self, svc_doc, svc_client, test_user):
        """Decrypted back photo matches original bytes."""
        original = b"fake_jpeg_bytes_back_photo_data"
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
            back_photo=original,
            back_photo_mime="image/png",
        )
        result = await svc_doc.get_back_photo(test_user.id, doc.id)
        assert result is not None
        photo_bytes, mime = result
        assert photo_bytes == original
        assert mime == "image/png"

    async def test_get_front_photo_nonexistent(self, svc_doc, svc_client, test_user):
        """Getting front photo when none exists returns None."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        result = await svc_doc.get_front_photo(test_user.id, doc.id)
        assert result is None

    async def test_get_back_photo_nonexistent(self, svc_doc, svc_client, test_user):
        """Getting back photo when none exists returns None."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        result = await svc_doc.get_back_photo(test_user.id, doc.id)
        assert result is None

    async def test_update_document_metadata(self, svc_doc, svc_client, test_user):
        """Update changes document metadata fields."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            document_number="ORIG001",
            issue_date=date(2024, 1, 1),
        )
        updated = await svc_doc.update(
            test_user.id,
            doc.id,
            document_number="UPDATED001",
            document_type="passport",
            expiry_date=date(2029, 1, 1),
        )
        assert updated.document_number == "UPDATED001"
        assert updated.document_type == "passport"
        assert updated.expiry_date == date(2029, 1, 1)

    async def test_update_duplicate_number_raises(self, svc_doc, svc_client, test_user):
        """Updating to an existing document number should raise."""
        client = await self._create_client(svc_client, test_user)
        await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            document_number="EXISTING",
            issue_date=date(2024, 1, 1),
        )
        doc2 = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="aadhaar",
            document_number="OTHER",
            issue_date=date(2024, 2, 1),
        )
        with pytest.raises(ValueError, match="already exists"):
            await svc_doc.update(test_user.id, doc2.id, document_number="EXISTING")

    async def test_soft_delete(self, svc_doc, svc_client, test_user):
        """Soft delete marks document as inactive."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        result = await svc_doc.soft_delete(test_user.id, doc.id)
        assert result is True
        with pytest.raises(UserNotFoundError):
            await svc_doc.get(test_user.id, doc.id)

    async def test_soft_delete_nonexistent(self, svc_doc, test_user):
        """Soft deleting a non-existent document returns False."""
        result = await svc_doc.soft_delete(test_user.id, uuid.uuid4())
        assert result is False

    async def test_list_excludes_inactive(self, svc_doc, svc_client, test_user):
        """List should exclude soft-deleted documents by default."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
        )
        await svc_doc.soft_delete(test_user.id, doc.id)
        docs, total = await svc_doc.list_all(test_user.id)
        assert doc.id not in [d.id for d in docs]

    async def test_has_front_photo_flag(self, svc_doc, svc_client, test_user):
        """Response metadata indicates presence of front photo."""
        client = await self._create_client(svc_client, test_user)
        doc_with = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
            front_photo=b"test",
            front_photo_mime="image/jpeg",
        )
        doc_without = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="aadhaar",
            issue_date=date(2024, 2, 1),
        )
        assert doc_with.front_photo_data is not None
        assert doc_without.front_photo_data is None

    async def test_batch_photos_returns_all(self, svc_doc, svc_client, test_user):
        """Batch returns front and back photos as base64 for all docs."""
        import base64

        front_orig = b"front_bytes_for_batch"
        back_orig = b"back_bytes_for_batch"
        client = await self._create_client(svc_client, test_user)
        doc1 = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
            front_photo=front_orig,
            front_photo_mime="image/jpeg",
        )
        doc2 = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="passport",
            issue_date=date(2024, 2, 1),
            back_photo=back_orig,
            back_photo_mime="image/png",
        )
        entries = await svc_doc.get_photos_batch(test_user.id, [doc1.id, doc2.id])
        assert len(entries) == 2

        e1 = next(e for e in entries if e["document_id"] == doc1.id)
        assert e1["front_photo_base64"] == base64.b64encode(front_orig).decode()
        assert e1["front_photo_mime"] == "image/jpeg"
        assert e1["back_photo_base64"] is None

        e2 = next(e for e in entries if e["document_id"] == doc2.id)
        assert e2["back_photo_base64"] == base64.b64encode(back_orig).decode()
        assert e2["back_photo_mime"] == "image/png"
        assert e2["front_photo_base64"] is None

    async def test_batch_photos_excludes_inactive(self, svc_doc, svc_client, test_user):
        """Soft-deleted documents are excluded from batch results."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
            front_photo=b"test",
            front_photo_mime="image/jpeg",
        )
        await svc_doc.soft_delete(test_user.id, doc.id)
        entries = await svc_doc.get_photos_batch(test_user.id, [doc.id])
        assert len(entries) == 0

    async def test_batch_photos_unknown_ids(self, svc_doc, test_user):
        """Non-existent document IDs are silently omitted."""
        entries = await svc_doc.get_photos_batch(test_user.id, [uuid.uuid4()])
        assert len(entries) == 0

    async def test_expiry_before_issue_raises_on_create(self, svc_doc, svc_client, test_user):
        """expiry_date before issue_date should raise ValueError on create."""
        client = await self._create_client(svc_client, test_user)
        with pytest.raises(ValueError, match="expiry_date must be after issue_date"):
            await svc_doc.create(
                user_id=test_user.id,
                client_id=client.id,
                document_type="pan_card",
                issue_date=date(2024, 6, 1),
                expiry_date=date(2024, 1, 1),
            )

    async def test_expiry_equal_to_issue_raises(self, svc_doc, svc_client, test_user):
        """expiry_date equal to issue_date should raise ValueError."""
        client = await self._create_client(svc_client, test_user)
        with pytest.raises(ValueError, match="expiry_date must be after issue_date"):
            await svc_doc.create(
                user_id=test_user.id,
                client_id=client.id,
                document_type="pan_card",
                issue_date=date(2024, 1, 1),
                expiry_date=date(2024, 1, 1),
            )

    async def test_expiry_before_issue_raises_on_update(self, svc_doc, svc_client, test_user):
        """Updating expiry before issue should raise ValueError."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="pan_card",
            issue_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
        )
        with pytest.raises(ValueError, match="expiry_date must be after issue_date"):
            await svc_doc.update(
                test_user.id,
                doc.id,
                expiry_date=date(2023, 1, 1),
            )

    async def test_list_documents_pagination(self, svc_doc, svc_client, test_user):
        """List respects offset and limit for documents."""
        client = await self._create_client(svc_client, test_user)
        for _ in range(10):
            await svc_doc.create(
                user_id=test_user.id,
                client_id=client.id,
                document_type="pan_card",
                issue_date=date(2024, 1, 1),
            )
        page1, total = await svc_doc.list_all(test_user.id, offset=0, limit=3)
        assert total == 10
        assert len(page1) == 3

        page2, total = await svc_doc.list_all(test_user.id, offset=3, limit=3)
        assert len(page2) == 3

    # ── Non-ID (filesystem) document tests ──────────────────────────

    async def test_create_non_id_document(
        self, svc_doc_with_storage, svc_client, test_user, tmp_path: Path,
    ):
        """Non-ID document stores encrypted file on filesystem, not in DB."""
        client = await self._create_client(svc_client, test_user)
        file_bytes = b"fake_will_pdf_content"
        doc = await svc_doc_with_storage.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="will",
            is_id=False,
            issue_date=date(2024, 6, 1),
            front_photo=file_bytes,
            front_photo_mime="application/pdf",
        )
        assert doc.id is not None
        assert doc.is_id is False
        assert doc.document_type == "will"
        assert doc.front_photo_data is None  # not in DB
        assert doc.front_photo_path is not None  # path on filesystem
        assert doc.back_photo_path is None

        # File exists on disk
        fs_path = tmp_path / doc.front_photo_path
        assert fs_path.exists()
        async with aiofiles.open(fs_path, "rb") as f:
            stored = await f.read()
        assert stored is not None  # encrypted bytes on disk

    async def test_non_id_front_photo_roundtrip(
        self, svc_doc_with_storage, svc_client, test_user,
    ):
        """Decrypted non-ID document file matches original bytes."""
        original = b"fake_will_pdf_content_for_test"
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc_with_storage.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="will",
            is_id=False,
            issue_date=date(2024, 6, 1),
            front_photo=original,
            front_photo_mime="application/pdf",
        )
        result = await svc_doc_with_storage.get_front_photo(test_user.id, doc.id)
        assert result is not None
        photo_bytes, mime = result
        assert photo_bytes == original
        assert mime == "application/pdf"

    async def test_non_id_get_back_photo_returns_none(
        self, svc_doc_with_storage, svc_client, test_user,
    ):
        """Non-ID documents never have a back photo."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc_with_storage.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="poa",
            is_id=False,
            issue_date=date(2024, 6, 1),
            front_photo=b"poa_content",
            front_photo_mime="image/png",
        )
        result = await svc_doc_with_storage.get_back_photo(test_user.id, doc.id)
        assert result is None

    async def test_hard_delete_cleans_filesystem_file(
        self, svc_doc_with_storage, svc_client, test_user, tmp_path: Path,
    ):
        """Hard-deleting a non-ID document removes its file from disk."""
        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc_with_storage.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="ekyc",
            is_id=False,
            issue_date=date(2024, 6, 1),
            front_photo=b"ekyc_content",
            front_photo_mime="image/jpeg",
        )
        path = doc.front_photo_path
        assert path is not None
        assert (tmp_path / path).exists()

        # Soft delete first, then hard delete
        await svc_doc_with_storage.soft_delete(test_user.id, doc.id)
        deleted = await svc_doc_with_storage.hard_delete(test_user.id, doc.id)
        assert deleted is True
        assert not (tmp_path / path).exists()

    async def test_batch_photos_includes_non_id_docs(
        self, svc_doc_with_storage, svc_client, test_user,
    ):
        """Batch photos returns filesystem-based documents correctly."""
        import base64

        client = await self._create_client(svc_client, test_user)
        doc = await svc_doc_with_storage.create(
            user_id=test_user.id,
            client_id=client.id,
            document_type="will",
            is_id=False,
            issue_date=date(2024, 6, 1),
            front_photo=b"batch_file_content",
            front_photo_mime="application/pdf",
        )
        entries = await svc_doc_with_storage.get_photos_batch(test_user.id, [doc.id])
        assert len(entries) == 1
        entry = entries[0]
        assert entry["document_id"] == doc.id
        assert entry["front_photo_base64"] == base64.b64encode(b"batch_file_content").decode()
        assert entry["front_photo_mime"] == "application/pdf"
        assert entry["back_photo_base64"] is None
