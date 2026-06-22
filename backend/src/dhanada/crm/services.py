"""Client management and document services."""

import base64
import csv
import hashlib
import io
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dhanada.auth.api import AuthManager
from dhanada.auth.crypto.envelope import EncryptedPayload, EnvelopeEncryption
from dhanada.auth.exceptions import (
    UserNotFoundError,
)
from dhanada.crm.models import Client, Document, DocumentType, normalize_pan, validate_pan


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

    async def create(self, user_id: UUID, name: str, pan: str) -> Client:
        await self._auth.assert_permission(user_id, "clients", "create")

        pan_normalized = normalize_pan(pan)
        if not validate_pan(pan_normalized):
            raise ValueError("Invalid PAN format (expected: AAAAA1234A)")

        pan_hash = hashlib.sha256(pan_normalized.encode()).hexdigest()
        encrypted = self._envelope.encrypt(pan_normalized.encode())

        client = await self._repo.create(
            name=name,
            pan_number_hash=pan_hash,
            encrypted_pan=encrypted.ciphertext,
            encrypted_nonce=encrypted.nonce,
            encrypted_dek=encrypted.encrypted_dek,
            created_by_id=user_id,
        )
        return client

    async def get(self, user_id: UUID, client_id: UUID) -> Client:
        await self._auth.assert_permission(user_id, "clients", "read")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise UserNotFoundError(f"Client {client_id} not found")
        return client

    async def list_all(
        self, user_id: UUID, search: str | None = None, include_inactive: bool = False
    ) -> list[Client]:
        await self._auth.assert_permission(user_id, "clients", "read")
        return await self._repo.list_all(search=search, include_inactive=include_inactive)

    async def update(self, user_id: UUID, client_id: UUID, name: str | None = None) -> Client:
        await self._auth.assert_permission(user_id, "clients", "edit")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise UserNotFoundError(f"Client {client_id} not found")

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if updates:
            updated = await self._repo.update(client_id, **updates)
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
        )
        return True

    async def get_pan(self, user_id: UUID, client_id: UUID) -> str:
        await self._auth.assert_permission(user_id, "clients", "manage-pan")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise UserNotFoundError(f"Client {client_id} not found")

        payload = EncryptedPayload.from_components(
            ciphertext=client.encrypted_pan,
            nonce=client.encrypted_nonce,
            encrypted_dek=client.encrypted_dek,
        )
        return self._envelope.decrypt(payload).decode()

    async def update_pan(self, user_id: UUID, client_id: UUID, pan: str) -> Client:
        await self._auth.assert_permission(user_id, "clients", "manage-pan")
        client = await self._repo.get(client_id)
        if client is None or not client.is_active:
            raise UserNotFoundError(f"Client {client_id} not found")

        pan_normalized = normalize_pan(pan)
        if not validate_pan(pan_normalized):
            raise ValueError("Invalid PAN format (expected: AAAAA1234A)")

        pan_hash = hashlib.sha256(pan_normalized.encode()).hexdigest()
        encrypted = self._envelope.encrypt(pan_normalized.encode())

        return await self._repo.update(
            client_id,
            pan_number_hash=pan_hash,
            encrypted_pan=encrypted.ciphertext,
            encrypted_nonce=encrypted.nonce,
            encrypted_dek=encrypted.encrypted_dek,
        )

    async def export_csv(self, user_id: UUID, include_pan: bool = False) -> str:
        await self._auth.assert_permission(user_id, "clients", "export")

        can_manage_pan = include_pan
        if include_pan:
            await self._auth.assert_permission(user_id, "clients", "manage-pan")

        clients = await self._repo.list_all(include_inactive=False)
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
        self, search: str | None = None, include_inactive: bool = False
    ) -> list[Client]:
        query = select(Client)
        if not include_inactive:
            query = query.where(Client.is_active.is_(True))
        if search:
            query = query.where(Client.name.ilike(f"%{search}%"))
        query = query.order_by(Client.created_at.desc())
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def update(self, client_id: UUID, **kwargs: Any) -> Client:
        result = await self._session.execute(
            update(Client).where(Client.id == client_id).values(**kwargs).returning(Client)
        )
        await self._session.flush()
        return result.scalar_one()


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        auth: AuthManager,
        envelope: EnvelopeEncryption,
    ) -> None:
        self._session = session
        self._auth = auth
        self._envelope = envelope

    async def create(
        self,
        user_id: UUID,
        client_id: UUID,
        document_type: str,
        issue_date: date,
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

        front_data, front_nonce, front_dek = None, None, None
        if front_photo is not None:
            encrypted = self._envelope.encrypt(front_photo)
            front_data = encrypted.ciphertext
            front_nonce = encrypted.nonce
            front_dek = encrypted.encrypted_dek

        back_data, back_nonce, back_dek = None, None, None
        if back_photo is not None:
            encrypted = self._envelope.encrypt(back_photo)
            back_data = encrypted.ciphertext
            back_nonce = encrypted.nonce
            back_dek = encrypted.encrypted_dek

        doc = Document(
            client_id=client_id,
            document_number=document_number,
            document_type=document_type,
            document_type_other=document_type_other,
            issue_date=issue_date,
            expiry_date=expiry_date,
            front_photo_data=front_data,
            front_photo_nonce=front_nonce,
            front_photo_dek=front_dek,
            front_photo_mime=front_photo_mime,
            back_photo_data=back_data,
            back_photo_nonce=back_nonce,
            back_photo_dek=back_dek,
            back_photo_mime=back_photo_mime,
            created_by_id=user_id,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def get(self, user_id: UUID, document_id: UUID) -> Document:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.is_active.is_(True))
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise UserNotFoundError(f"Document {document_id} not found")
        return doc

    async def list_all(
        self,
        user_id: UUID,
        client_id: UUID | None = None,
        document_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[Document]:
        await self._auth.assert_permission(user_id, "documents", "read")
        query = select(Document)
        if not include_inactive:
            query = query.where(Document.is_active.is_(True))
        if client_id:
            query = query.where(Document.client_id == client_id)
        if document_type:
            query = query.where(Document.document_type == document_type)
        query = query.order_by(Document.created_at.desc())
        result = await self._session.execute(query)
        return list(result.scalars().all())

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
            updates["expiry_date"] = expiry_date

        if updates:
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
            )
        )
        await self._session.flush()
        return True

    async def get_front_photo(self, user_id: UUID, document_id: UUID) -> tuple[bytes, str] | None:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.is_active.is_(True))
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise UserNotFoundError(f"Document {document_id} not found")
        if doc.front_photo_data is None:
            return None
        assert doc.front_photo_nonce is not None
        assert doc.front_photo_dek is not None
        assert doc.front_photo_mime is not None
        payload = EncryptedPayload.from_components(
            ciphertext=doc.front_photo_data,
            nonce=doc.front_photo_nonce,
            encrypted_dek=doc.front_photo_dek,
        )
        return self._envelope.decrypt(payload), doc.front_photo_mime

    async def get_back_photo(self, user_id: UUID, document_id: UUID) -> tuple[bytes, str] | None:
        await self._auth.assert_permission(user_id, "documents", "read")
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.is_active.is_(True))
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise UserNotFoundError(f"Document {document_id} not found")
        if doc.back_photo_data is None:
            return None
        assert doc.back_photo_nonce is not None
        assert doc.back_photo_dek is not None
        assert doc.back_photo_mime is not None
        payload = EncryptedPayload.from_components(
            ciphertext=doc.back_photo_data,
            nonce=doc.back_photo_nonce,
            encrypted_dek=doc.back_photo_dek,
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
            if doc.front_photo_data is not None:
                assert doc.front_photo_nonce is not None
                assert doc.front_photo_dek is not None
                payload = EncryptedPayload.from_components(
                    ciphertext=doc.front_photo_data,
                    nonce=doc.front_photo_nonce,
                    encrypted_dek=doc.front_photo_dek,
                )
                front_base64 = base64.b64encode(self._envelope.decrypt(payload)).decode()
                front_mime = doc.front_photo_mime

            back_base64, back_mime = None, None
            if doc.back_photo_data is not None:
                assert doc.back_photo_nonce is not None
                assert doc.back_photo_dek is not None
                payload = EncryptedPayload.from_components(
                    ciphertext=doc.back_photo_data,
                    nonce=doc.back_photo_nonce,
                    encrypted_dek=doc.back_photo_dek,
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
