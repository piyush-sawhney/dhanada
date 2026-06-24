"""Client management and document services."""

import base64
import csv
import hmac
import io
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dhanada.auth.api import AuthManager
from dhanada.auth.crypto.envelope import EncryptedPayload, EnvelopeEncryption
from dhanada.crm.exceptions import ClientNotFoundError, DocumentNotFoundError
from dhanada.crm.models import Client, Document, DocumentType
from dhanada.crm.pan import normalize_pan, validate_pan
from dhanada.crm.storage import StorageBackend

_ID_PHOTO_MAX_SIZE = 2 * 1024 * 1024  # 2 MB
_ID_PHOTO_ALLOWED_MIMES = {"image/jpeg", "image/jpg", "image/png"}


class ClientService:
    def __init__(
        self,
        session: AsyncSession,
        auth: AuthManager,
        envelope: EnvelopeEncryption,
    ) -> None:
        self._session = session
        self._auth = auth
        self._envelope = envelope
        self._repo = _ClientRepository(session)
        self._pan_hmac_key = auth.config.pan_hmac_key.encode()

    async def create(self, user_id: UUID, name: str, pan: str) -> Client:
        await self._auth.assert_permission(user_id, "clients", "create")

        pan_normalized = normalize_pan(pan)
        if not validate_pan(pan_normalized):
            raise ValueError("Invalid PAN format (expected: AAAAA1234A)")

        pan_hash = hmac.new(self._pan_hmac_key, pan_normalized.encode(), "sha256").hexdigest()

        existing = await self._session.execute(
            select(Client).where(Client.pan_number_hash == pan_hash)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("A client with this PAN already exists")

        encrypted = self._envelope.encrypt(pan_normalized.encode())

        client = await self._repo.create(
            name=name,
            pan_number_hash=pan_hash,
            encrypted_pan=encrypted.ciphertext,
            encrypted_nonce=encrypted.nonce,
            encrypted_dek=encrypted.encrypted_dek,
            pan_encryption_key_id=encrypted.key_id,
            created_by_id=user_id,
        )
        return client

    async def get(self, user_id: UUID, client_id: UUID) -> Client:
        await self._auth.assert_permission(user_id, "clients", "read")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise ClientNotFoundError(f"Client {client_id} not found")
        return client

    async def list_all(
        self,
        user_id: UUID,
        search: str | None = None,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Client], int]:
        await self._auth.assert_permission(user_id, "clients", "read")
        return await self._repo.list_all(
            search=search,
            include_inactive=include_inactive,
            offset=offset,
            limit=limit,
        )

    async def update(self, user_id: UUID, client_id: UUID, name: str | None = None) -> Client:
        await self._auth.assert_permission(user_id, "clients", "edit")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise ClientNotFoundError(f"Client {client_id} not found")

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if updates:
            updated = await self._repo.update(client_id, **updates, updated_by_id=user_id)
            return updated
        return client

    async def soft_delete(self, user_id: UUID, client_id: UUID) -> bool:
        await self._auth.assert_permission(user_id, "clients", "delete")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            return False

        await self._repo.update(
            client_id,
            is_active=False,
            deleted_at=datetime.now(UTC),
            deleted_by_id=user_id,
            updated_by_id=user_id,
        )
        return True

    async def restore(self, user_id: UUID, client_id: UUID) -> Client:
        await self._auth.assert_permission(user_id, "clients", "delete")
        client = await self._repo.get(client_id)
        if client is None:
            raise ClientNotFoundError(f"Client {client_id} not found")
        if client.is_active:
            return client
        return await self._repo.update(
            client_id,
            is_active=True,
            deleted_at=None,
            deleted_by_id=None,
            updated_by_id=user_id,
        )

    async def hard_delete(self, user_id: UUID, client_id: UUID) -> bool:
        await self._auth.assert_permission(user_id, "clients", "delete")
        client = await self._repo.get(client_id)
        if client is None or client.is_active:
            return False
        return await self._repo.hard_delete(client_id)

    async def get_pan(self, user_id: UUID, client_id: UUID) -> str:
        await self._auth.assert_permission(user_id, "clients", "manage-pan")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise ClientNotFoundError(f"Client {client_id} not found")

        payload = EncryptedPayload.from_components(
            ciphertext=client.encrypted_pan,
            nonce=client.encrypted_nonce,
            encrypted_dek=client.encrypted_dek,
            key_id=client.pan_encryption_key_id,
        )
        return self._envelope.decrypt(payload).decode()

    async def update_pan(self, user_id: UUID, client_id: UUID, pan: str) -> Client:
        await self._auth.assert_permission(user_id, "clients", "manage-pan")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise ClientNotFoundError(f"Client {client_id} not found")

        pan_normalized = normalize_pan(pan)
        if not validate_pan(pan_normalized):
            raise ValueError("Invalid PAN format (expected: AAAAA1234A)")

        pan_hash = hmac.new(self._pan_hmac_key, pan_normalized.encode(), "sha256").hexdigest()
        encrypted = self._envelope.encrypt(pan_normalized.encode())

        return await self._repo.update(
            client_id,
            pan_number_hash=pan_hash,
            encrypted_pan=encrypted.ciphertext,
            encrypted_nonce=encrypted.nonce,
            encrypted_dek=encrypted.encrypted_dek,
            pan_encryption_key_id=encrypted.key_id,
            updated_by_id=user_id,
        )

    async def get_with_pan(self, user_id: UUID, client_id: UUID) -> tuple[Client, str]:
        await self._auth.assert_permission(user_id, "clients", "read")
        await self._auth.assert_permission(user_id, "clients", "manage-pan")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise ClientNotFoundError(f"Client {client_id} not found")

        payload = EncryptedPayload.from_components(
            ciphertext=client.encrypted_pan,
            nonce=client.encrypted_nonce,
            encrypted_dek=client.encrypted_dek,
            key_id=client.pan_encryption_key_id,
        )
        pan = self._envelope.decrypt(payload).decode()
        return client, pan

    async def export_csv(self, user_id: UUID) -> str:
        await self._auth.assert_permission(user_id, "clients", "export")

        perm = await self._auth.check_permission(user_id, "clients", "manage-pan")
        can_manage_pan = perm.allowed

        clients, _ = await self._repo.list_all(include_inactive=False, limit=10000)
        output = io.StringIO()
        writer = csv.writer(output)
        header = ["id", "name", "is_active", "created_at", "updated_at"]
        if can_manage_pan:
            header.append("pan")
        writer.writerow(header)

        for c in clients:
            row = [
                str(c.id),
                c.name,
                c.is_active,
                c.created_at.isoformat() if c.created_at else "",
                c.updated_at.isoformat() if c.updated_at else "",
            ]
            if can_manage_pan:
                payload = EncryptedPayload.from_components(
                    ciphertext=c.encrypted_pan,
                    nonce=c.encrypted_nonce,
                    encrypted_dek=c.encrypted_dek,
                    key_id=c.pan_encryption_key_id,
                )
                pan = self._envelope.decrypt(payload).decode()
                row.append(pan)
            writer.writerow(row)

        return output.getvalue()


class _ClientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs: Any) -> Client:
        client = Client(**kwargs)
        self._session.add(client)
        await self._session.flush()
        return client

    async def get(self, client_id: UUID) -> Client | None:
        result = await self._session.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        search: str | None = None,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Client], int]:
        conditions = []
        if not include_inactive:
            conditions.append(Client.is_active.is_(True))
        if search:
            conditions.append(Client.name.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(Client)
        if conditions:
            count_query = count_query.where(*conditions)
        total = (await self._session.execute(count_query)).scalar_one()

        query = select(Client)
        if conditions:
            query = query.where(*conditions)
        query = query.order_by(Client.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def update(self, client_id: UUID, **kwargs: Any) -> Client:
        result = await self._session.execute(
            update(Client).where(Client.id == client_id).values(**kwargs).returning(Client)
        )
        await self._session.flush()
        return result.scalar_one()

    async def hard_delete(self, client_id: UUID) -> bool:
        result = await self._session.execute(delete(Client).where(Client.id == client_id))
        await self._session.flush()
        return cast(bool, result.rowcount > 0)


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        auth: AuthManager,
        envelope: EnvelopeEncryption,
        storage: StorageBackend | None = None,
    ) -> None:
        self._session = session
        self._auth = auth
        self._envelope = envelope
        self._storage = storage

    async def create(
        self,
        user_id: UUID,
        client_id: UUID,
        document_type: str,
        issue_date: date,
        is_id: bool = True,
        document_number: str | None = None,
        expiry_date: date | None = None,
        document_type_other: str | None = None,
        front_photo: bytes | None = None,
        front_photo_mime: str | None = None,
        back_photo: bytes | None = None,
        back_photo_mime: str | None = None,
    ) -> Document:
        await self._auth.assert_permission(user_id, "documents", "create")

        if document_number:
            existing = await self._session.execute(
                select(Document).where(Document.document_number == document_number)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Document number '{document_number}' already exists")

        if document_type == DocumentType.OTHER.value and not document_type_other:
            raise ValueError("document_type_other is required when document_type is 'other'")

        if expiry_date and expiry_date <= issue_date:
            raise ValueError("expiry_date must be after issue_date")

        if is_id:
            if front_photo is not None:
                if len(front_photo) > _ID_PHOTO_MAX_SIZE:
                    raise ValueError("front_photo exceeds 2 MB limit")
                if front_photo_mime and front_photo_mime not in _ID_PHOTO_ALLOWED_MIMES:
                    raise ValueError("front_photo must be JPEG or PNG")
            if back_photo is not None:
                if len(back_photo) > _ID_PHOTO_MAX_SIZE:
                    raise ValueError("back_photo exceeds 2 MB limit")
                if back_photo_mime and back_photo_mime not in _ID_PHOTO_ALLOWED_MIMES:
                    raise ValueError("back_photo must be JPEG or PNG")

        kwargs: dict[str, Any] = {
            "client_id": client_id,
            "document_number": document_number,
            "document_type": document_type,
            "document_type_other": document_type_other,
            "issue_date": issue_date,
            "expiry_date": expiry_date,
            "is_id": is_id,
            "created_by_id": user_id,
        }

        if is_id:
            if front_photo is not None:
                encrypted = self._envelope.encrypt(front_photo)
                kwargs["front_photo_data"] = encrypted.ciphertext
                kwargs["front_photo_nonce"] = encrypted.nonce
                kwargs["front_photo_dek"] = encrypted.encrypted_dek
                kwargs["front_photo_key_id"] = encrypted.key_id
                kwargs["front_photo_mime"] = front_photo_mime

            if back_photo is not None:
                encrypted = self._envelope.encrypt(back_photo)
                kwargs["back_photo_data"] = encrypted.ciphertext
                kwargs["back_photo_nonce"] = encrypted.nonce
                kwargs["back_photo_dek"] = encrypted.encrypted_dek
                kwargs["back_photo_key_id"] = encrypted.key_id
                kwargs["back_photo_mime"] = back_photo_mime

            doc = Document(**kwargs)
            self._session.add(doc)
            await self._session.flush()
            return doc

        # Non-ID documents: encrypted on filesystem
        front_encrypted = self._envelope.encrypt(front_photo) if front_photo else None
        if front_encrypted:
            kwargs["front_photo_nonce"] = front_encrypted.nonce
            kwargs["front_photo_dek"] = front_encrypted.encrypted_dek
            kwargs["front_photo_key_id"] = front_encrypted.key_id
            kwargs["front_photo_mime"] = front_photo_mime

        doc = Document(**kwargs)
        self._session.add(doc)
        await self._session.flush()

        if front_encrypted and self._storage is not None:
            path = await self._storage.store(doc.id, "file", front_encrypted.ciphertext)
            doc.front_photo_path = path
            await self._session.flush()

        return doc

    async def get(self, user_id: UUID, document_id: UUID) -> Document:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.is_active.is_(True))
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return doc

    async def list_all(
        self,
        user_id: UUID,
        client_id: UUID | None = None,
        document_type: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Document], int]:
        await self._auth.assert_permission(user_id, "documents", "read")
        conditions = []
        if not include_inactive:
            conditions.append(Document.is_active.is_(True))
        if client_id:
            conditions.append(Document.client_id == client_id)
        if document_type:
            conditions.append(Document.document_type == document_type)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                Document.document_number.ilike(pattern) | Document.document_type.ilike(pattern)
            )

        count_query = select(func.count()).select_from(Document)
        if conditions:
            count_query = count_query.where(*conditions)
        total = (await self._session.execute(count_query)).scalar_one()

        query = select(Document)
        if conditions:
            query = query.where(*conditions)
        query = query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def update(
        self,
        user_id: UUID,
        document_id: UUID,
        document_number: str | None = None,
        document_type: str | None = None,
        document_type_other: str | None = None,
        issue_date: date | None = None,
        expiry_date: date | None = None,
    ) -> Document:
        await self._auth.assert_permission(user_id, "documents", "edit")
        doc = await self.get(user_id, document_id)

        updates: dict[str, Any] = {}
        if document_number is not None:
            existing = await self._session.execute(
                select(Document).where(
                    Document.document_number == document_number,
                    Document.id != document_id,
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Document number '{document_number}' already exists")
            updates["document_number"] = document_number
        if document_type is not None:
            updates["document_type"] = document_type
        if document_type_other is not None:
            updates["document_type_other"] = document_type_other
        if issue_date is not None:
            updates["issue_date"] = issue_date
        if expiry_date is not None:
            effective_issue = issue_date if issue_date is not None else doc.issue_date
            if expiry_date <= effective_issue:
                raise ValueError("expiry_date must be after issue_date")
            updates["expiry_date"] = expiry_date

        if updates:
            updates["updated_by_id"] = user_id
            result = await self._session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(**updates)
                .returning(Document)
            )
            await self._session.flush()
            return result.scalar_one()
        return doc

    async def soft_delete(self, user_id: UUID, document_id: UUID) -> bool:
        await self._auth.assert_permission(user_id, "documents", "delete")
        result = await self._session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None or not doc.is_active:
            return False
        await self._session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(
                is_active=False,
                deleted_at=datetime.now(UTC),
                deleted_by_id=user_id,
                updated_by_id=user_id,
            )
        )
        await self._session.flush()
        return True

    async def restore(self, user_id: UUID, document_id: UUID) -> Document:
        await self._auth.assert_permission(user_id, "documents", "delete")
        result = await self._session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if doc.is_active:
            return doc
        result = await self._session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(is_active=True, deleted_at=None, deleted_by_id=None, updated_by_id=user_id)
            .returning(Document)
        )
        await self._session.flush()
        return result.scalar_one()

    async def hard_delete(self, user_id: UUID, document_id: UUID) -> bool:
        await self._auth.assert_permission(user_id, "documents", "delete")
        result = await self._session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None or doc.is_active:
            return False

        if not doc.is_id and self._storage is not None and doc.front_photo_path:
            await self._storage.delete(doc.front_photo_path)

        await self._session.execute(delete(Document).where(Document.id == document_id))
        await self._session.flush()
        return True

    async def _get_ciphertext(self, doc: Document, side: str) -> bytes | None:
        """Resolve the encrypted ciphertext for a document photo/file.

        For ID documents the ciphertext is stored in a ``LargeBinary`` column.
        For other documents it is read from the filesystem.
        """
        if doc.is_id:
            return getattr(doc, f"{side}_photo_data", None)

        path: str | None = getattr(doc, f"{side}_photo_path", None)
        if path is None or self._storage is None:
            return None
        return await self._storage.retrieve(path)

    async def get_front_photo(self, user_id: UUID, document_id: UUID) -> tuple[bytes, str] | None:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.is_active.is_(True))
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        ciphertext = await self._get_ciphertext(doc, "front")
        if ciphertext is None:
            return None
        if not all([doc.front_photo_nonce, doc.front_photo_dek, doc.front_photo_mime]):
            raise ValueError(
                "Inconsistent encryption state: front photo data present but missing nonce/DEK/MIME"
            )
        payload = EncryptedPayload.from_components(
            ciphertext=ciphertext,
            nonce=doc.front_photo_nonce,
            encrypted_dek=doc.front_photo_dek,
            key_id=doc.front_photo_key_id,
        )
        return self._envelope.decrypt(payload), doc.front_photo_mime

    async def get_back_photo(self, user_id: UUID, document_id: UUID) -> tuple[bytes, str] | None:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.is_active.is_(True))
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if not doc.is_id:
            return None
        if doc.back_photo_data is None:
            return None
        if not all([doc.back_photo_nonce, doc.back_photo_dek, doc.back_photo_mime]):
            raise ValueError(
                "Inconsistent encryption state: back_photo_data present but missing nonce/DEK/MIME"
            )
        payload = EncryptedPayload.from_components(
            ciphertext=doc.back_photo_data,
            nonce=doc.back_photo_nonce,
            encrypted_dek=doc.back_photo_dek,
            key_id=doc.back_photo_key_id,
        )
        return self._envelope.decrypt(payload), doc.back_photo_mime

    async def get_photos_batch(
        self, user_id: UUID, document_ids: list[UUID]
    ) -> list[dict[str, Any]]:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(
                Document.id.in_(document_ids),
                Document.is_active.is_(True),
            )
        )
        docs = result.scalars().all()

        entries = []
        for doc in docs:
            front_base64, front_mime = None, None
            ciphertext = await self._get_ciphertext(doc, "front")
            if ciphertext is not None:
                if doc.front_photo_nonce is None or doc.front_photo_dek is None:
                    raise ValueError(
                        "Inconsistent state: front photo data present but missing nonce/DEK"
                    )
                payload = EncryptedPayload.from_components(
                    ciphertext=ciphertext,
                    nonce=doc.front_photo_nonce,
                    encrypted_dek=doc.front_photo_dek,
                    key_id=doc.front_photo_key_id,
                )
                front_base64 = base64.b64encode(self._envelope.decrypt(payload)).decode()
                front_mime = doc.front_photo_mime

            back_base64, back_mime = None, None
            if doc.is_id and doc.back_photo_data is not None:
                if doc.back_photo_nonce is None or doc.back_photo_dek is None:
                    raise ValueError(
                        "Inconsistent state: back_photo_data present but missing nonce/DEK"
                    )
                payload = EncryptedPayload.from_components(
                    ciphertext=doc.back_photo_data,
                    nonce=doc.back_photo_nonce,
                    encrypted_dek=doc.back_photo_dek,
                    key_id=doc.back_photo_key_id,
                )
                back_base64 = base64.b64encode(self._envelope.decrypt(payload)).decode()
                back_mime = doc.back_photo_mime

            entries.append(
                {
                    "document_id": doc.id,
                    "front_photo_base64": front_base64,
                    "front_photo_mime": front_mime,
                    "back_photo_base64": back_base64,
                    "back_photo_mime": back_mime,
                }
            )
        return entries
