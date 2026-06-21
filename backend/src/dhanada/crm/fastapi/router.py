"""FastAPI router for CRM endpoints."""

import io
from collections.abc import AsyncGenerator
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from dhanada.auth.api import AuthManager
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.exceptions import PermissionDeniedError
from dhanada.auth.fastapi.dependencies import get_auth_manager, get_current_user
from dhanada.auth.models.user import User
from dhanada.crm.fastapi.schemas import (
    ClientCreateRequest,
    ClientDetailResponse,
    ClientPanUpdateRequest,
    ClientResponse,
    ClientUpdateRequest,
    DocumentBatchPhotosRequest,
    DocumentBatchPhotosResponse,
    DocumentPhotoEntry,
    DocumentResponse,
    DocumentUpdateRequest,
)
from dhanada.crm.services import ClientService, DocumentService

crm_router = APIRouter(prefix="/api/crm", tags=["crm"])


async def get_client_service(
    auth: AuthManager = Depends(get_auth_manager),
) -> AsyncGenerator[ClientService, None]:
    """Dependency that creates a ClientService with a tracked DB session."""
    db = DatabaseSession(str(auth.config.database_url))
    try:
        async with db.session() as session:
            yield ClientService(session=session, auth=auth, envelope=auth._envelope)
    finally:
        await db.close()


@crm_router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    body: ClientCreateRequest,
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    """Create a new client. Requires clients:create permission."""
    try:
        client = await service.create(user.id, body.name, body.pan)
        return ClientResponse.model_validate(client)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@crm_router.get("/clients", response_model=list[ClientResponse])
async def list_clients(
    search: str | None = Query(None, max_length=255),
    include_inactive: bool = Query(False),
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> list[ClientResponse]:
    """List clients. Requires clients:read permission."""
    clients = await service.list(user.id, search=search, include_inactive=include_inactive)
    return [ClientResponse.model_validate(c) for c in clients]


@crm_router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    """Get a client by ID. Requires clients:read permission."""
    try:
        client = await service.get(user.id, client_id)
        return ClientResponse.model_validate(client)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@crm_router.patch("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    body: ClientUpdateRequest,
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    """Update client name. Requires clients:edit permission."""
    try:
        client = await service.update(user.id, client_id, name=body.name)
        return ClientResponse.model_validate(client)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@crm_router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> None:
    """Soft-delete a client. Requires clients:delete permission."""
    deleted = await service.soft_delete(user.id, client_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@crm_router.get("/clients/{client_id}/pan", response_model=ClientDetailResponse)
async def get_client_pan(
    client_id: UUID,
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> ClientDetailResponse:
    """Get client with decrypted PAN. Requires clients:manage-pan permission."""
    try:
        client = await service.get(user.id, client_id)
        pan = await service.get_pan(user.id, client_id)
        resp = ClientDetailResponse.model_validate(client)
        resp.pan = pan
        return resp
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@crm_router.patch("/clients/{client_id}/pan", response_model=ClientResponse)
async def update_client_pan(
    client_id: UUID,
    body: ClientPanUpdateRequest,
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    """Update PAN for a client. Requires clients:manage-pan permission."""
    try:
        client = await service.update_pan(user.id, client_id, body.pan)
        return ClientResponse.model_validate(client)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@crm_router.post("/clients/export")
async def export_clients(
    include_pan: bool = Query(False),
    user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
) -> StreamingResponse:
    """Export clients as CSV. Requires clients:export permission.

    If include_pan=true, also requires clients:manage-pan permission.
    """
    csv_content = await service.export_csv(user.id, include_pan=include_pan)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients.csv"},
    )


ALLOWED_PHOTO_MIMES = {"image/jpeg", "image/jpg", "image/png"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024


async def get_document_service(
    auth: AuthManager = Depends(get_auth_manager),
) -> AsyncGenerator[DocumentService, None]:
    """Dependency that creates a DocumentService with a tracked DB session."""
    db = DatabaseSession(str(auth.config.database_url))
    try:
        async with db.session() as session:
            yield DocumentService(session=session, auth=auth, envelope=auth._envelope)
    finally:
        await db.close()


@crm_router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    client_id: UUID = Form(...),
    document_type: str = Form(...),
    issue_date: date = Form(...),
    document_number: str | None = Form(None),
    expiry_date: date | None = Form(None),
    document_type_other: str | None = Form(None),
    front_photo: UploadFile | None = File(None),
    back_photo: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Upload a document for a client. Requires documents:create permission."""
    try:
        front_bytes, front_mime = None, None
        if front_photo:
            if front_photo.content_type not in ALLOWED_PHOTO_MIMES:
                raise HTTPException(400, "front_photo must be JPEG or PNG")
            front_bytes = await front_photo.read()
            if len(front_bytes) > MAX_PHOTO_SIZE:
                raise HTTPException(400, "front_photo exceeds 5MB limit")
            front_mime = front_photo.content_type

        back_bytes, back_mime = None, None
        if back_photo:
            if back_photo.content_type not in ALLOWED_PHOTO_MIMES:
                raise HTTPException(400, "back_photo must be JPEG or PNG")
            back_bytes = await back_photo.read()
            if len(back_bytes) > MAX_PHOTO_SIZE:
                raise HTTPException(400, "back_photo exceeds 5MB limit")
            back_mime = back_photo.content_type

        doc = await service.create(
            user_id=user.id,
            client_id=client_id,
            document_type=document_type,
            issue_date=issue_date,
            document_number=document_number or None,
            expiry_date=expiry_date,
            document_type_other=document_type_other,
            front_photo=front_bytes,
            front_photo_mime=front_mime,
            back_photo=back_bytes,
            back_photo_mime=back_mime,
        )
        return DocumentResponse.from_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@crm_router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    client_id: UUID | None = Query(None),
    document_type: str | None = Query(None, max_length=50),
    include_inactive: bool = Query(False),
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    """List documents. Requires documents:read permission."""
    docs = await service.list(
        user.id,
        client_id=client_id,
        document_type=document_type,
        include_inactive=include_inactive,
    )
    return [DocumentResponse.from_document(d) for d in docs]


@crm_router.post("/documents/photos/batch", response_model=DocumentBatchPhotosResponse)
async def batch_document_photos(
    body: DocumentBatchPhotosRequest,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentBatchPhotosResponse:
    """Get front and back photos for up to 50 documents in batch.
    Requires documents:read permission. Missing photos return as null."""
    entries = await service.get_photos_batch(user.id, body.document_ids)
    return DocumentBatchPhotosResponse(
        photos=[DocumentPhotoEntry(**e) for e in entries]
    )


@crm_router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Get a document by ID (metadata only, no photos). Requires documents:read permission."""
    try:
        doc = await service.get(user.id, document_id)
        return DocumentResponse.from_document(doc)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@crm_router.get("/documents/{document_id}/photo/front")
async def get_document_front_photo(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> StreamingResponse:
    """Stream decrypted front photo. Requires documents:read permission."""
    try:
        result = await service.get_front_photo(user.id, document_id)
        if result is None:
            raise HTTPException(status_code=404, detail="No front photo")
        photo_bytes, mime = result
        return StreamingResponse(
            io.BytesIO(photo_bytes),
            media_type=mime,
            headers={"Content-Disposition": "inline"},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@crm_router.get("/documents/{document_id}/photo/back")
async def get_document_back_photo(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> StreamingResponse:
    """Stream decrypted back photo. Requires documents:read permission."""
    try:
        result = await service.get_back_photo(user.id, document_id)
        if result is None:
            raise HTTPException(status_code=404, detail="No back photo")
        photo_bytes, mime = result
        return StreamingResponse(
            io.BytesIO(photo_bytes),
            media_type=mime,
            headers={"Content-Disposition": "inline"},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@crm_router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    body: DocumentUpdateRequest,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Update document metadata. Requires documents:edit permission."""
    try:
        doc = await service.update(
            user.id,
            document_id,
            document_number=body.document_number,
            document_type=body.document_type,
            document_type_other=body.document_type_other,
            issue_date=body.issue_date,
            expiry_date=body.expiry_date,
        )
        return DocumentResponse.from_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@crm_router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> None:
    """Soft-delete a document. Requires documents:delete permission."""
    deleted = await service.soft_delete(user.id, document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
