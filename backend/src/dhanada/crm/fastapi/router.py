"""FastAPI router for CRM endpoints."""

import io
from collections.abc import AsyncGenerator
from datetime import date
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from dhanada.auth.api import AuthManager
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.exceptions import PermissionDeniedError, UserNotFoundError
from dhanada.auth.fastapi.dependencies import get_auth_manager, get_current_user
from dhanada.auth.models.user import User
from dhanada.auth.rate_limit import limiter
from dhanada.crm.fastapi.schemas import (
    ClientCreateRequest,
    ClientDetailResponse,
    ClientListParams,
    ClientPanUpdateRequest,
    ClientResponse,
    ClientUpdateRequest,
    DocumentBatchPhotosRequest,
    DocumentBatchPhotosResponse,
    DocumentPhotoEntry,
    DocumentResponse,
    DocumentUpdateRequest,
    PaginatedResponse,
)
from dhanada.crm.services import ClientService, DocumentService
from dhanada.crm.storage import LocalFileStorage

crm_router = APIRouter(prefix="/api/crm", tags=["crm"])


async def get_client_service(
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> AsyncGenerator[ClientService, None]:
    """Dependency that creates a ClientService with a tracked DB session."""
    db = DatabaseSession(str(auth.config.database_url))
    try:
        async with db.session() as session:
            yield ClientService(session=session, auth=auth, envelope=auth.envelope)
    finally:
        await db.close()


@crm_router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_client(
    body: ClientCreateRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> ClientResponse:
    """Create a new client. Requires clients:create permission."""
    try:
        client = await service.create(user.id, body.name, body.pan)
        return ClientResponse.model_validate(client)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from None


@crm_router.get("/clients", response_model=PaginatedResponse[ClientResponse])
@limiter.limit("60/minute")
async def list_clients(
    request: Request,  # noqa: ARG001
    params: ClientListParams = Depends(),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> PaginatedResponse[ClientResponse]:
    """List clients. Requires clients:read permission."""
    include_inactive = params.status == "all" or params.status == "inactive"
    clients, total = await service.list_all(
        user.id,
        search=params.search,
        include_inactive=include_inactive,
        offset=params.offset,
        limit=params.limit,
    )
    return PaginatedResponse(
        items=[ClientResponse.model_validate(c) for c in clients],
        total=total,
        offset=params.offset,
        limit=params.limit,
    )


@crm_router.get("/clients/{client_id}", response_model=ClientResponse)
@limiter.limit("60/minute")
async def get_client(
    client_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> ClientResponse:
    """Get a client by ID. Requires clients:read permission."""
    try:
        client = await service.get(user.id, client_id)
        return ClientResponse.model_validate(client)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        ) from None


@crm_router.patch("/clients/{client_id}", response_model=ClientResponse)
@limiter.limit("30/minute")
async def update_client(
    client_id: UUID,
    body: ClientUpdateRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> ClientResponse:
    """Update client name. Requires clients:edit permission."""
    try:
        client = await service.update(user.id, client_id, name=body.name)
        return ClientResponse.model_validate(client)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        ) from None


@crm_router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_client(
    client_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> None:
    """Soft-delete a client. Requires clients:delete permission."""
    deleted = await service.soft_delete(user.id, client_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        ) from None


@crm_router.post("/clients/{client_id}/restore", response_model=ClientResponse)
@limiter.limit("20/minute")
async def restore_client(
    client_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> ClientResponse:
    """Restore a soft-deleted client. Requires clients:delete permission."""
    try:
        client = await service.restore(user.id, client_id)
        return ClientResponse.model_validate(client)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        ) from None


@crm_router.delete("/clients/{client_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def hard_delete_client(
    client_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> None:
    """Permanently delete a soft-deleted client. Requires clients:delete permission."""
    deleted = await service.hard_delete(user.id, client_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found or still active"
        ) from None


@crm_router.get("/clients/{client_id}/pan", response_model=ClientDetailResponse)
@limiter.limit("30/minute")
async def get_client_pan(
    client_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> ClientDetailResponse:
    """Get client with decrypted PAN. Requires clients:manage-pan permission."""
    try:
        client, pan = await service.get_with_pan(user.id, client_id)
        resp = ClientDetailResponse.model_validate(client)
        resp.pan = pan
        return resp
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        ) from None


@crm_router.patch("/clients/{client_id}/pan", response_model=ClientResponse)
@limiter.limit("20/minute")
async def update_client_pan(
    client_id: UUID,
    body: ClientPanUpdateRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> ClientResponse:
    """Update PAN for a client. Requires clients:manage-pan permission."""
    try:
        client = await service.update_pan(user.id, client_id, body.pan)
        return ClientResponse.model_validate(client)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        ) from None


@crm_router.post("/clients/export")
@limiter.limit("10/minute")
async def export_clients(
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: ClientService = Depends(get_client_service),  # noqa: B008
) -> StreamingResponse:
    """Export clients as CSV. Requires clients:export permission.
    PAN is included automatically if user has clients:manage-pan permission.
    """
    csv_content = await service.export_csv(user.id)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients.csv"},
    )


ALLOWED_PHOTO_MIMES = {"image/jpeg", "image/jpg", "image/png"}
MAX_ID_PHOTO_SIZE = 2 * 1024 * 1024  # 2MB for DB storage


async def get_document_service(
    auth: AuthManager = Depends(get_auth_manager),  # noqa: B008
) -> AsyncGenerator[DocumentService, None]:
    """Dependency that creates a DocumentService with a tracked DB session."""
    db = DatabaseSession(str(auth.config.database_url))
    storage = LocalFileStorage(auth.config.document_storage_path)
    try:
        async with db.session() as session:
            yield DocumentService(
                session=session,
                auth=auth,
                envelope=auth.envelope,
                storage=storage,
            )
    finally:
        await db.close()


@crm_router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_document(
    request: Request,  # noqa: ARG001
    client_id: UUID = Form(...),  # noqa: B008
    document_type: str = Form(...),  # noqa: B008
    is_id: bool = Form(True),  # noqa: B008
    issue_date: date = Form(...),  # noqa: B008
    document_number: str | None = Form(None),  # noqa: B008
    expiry_date: date | None = Form(None),  # noqa: B008
    document_type_other: str | None = Form(None),  # noqa: B008
    front_photo: UploadFile | None = File(None),  # noqa: B008
    back_photo: UploadFile | None = File(None),  # noqa: B008
    file: UploadFile | None = File(None),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> DocumentResponse:
    """Upload a document for a client. Requires documents:create permission.

    - **ID documents** (``is_id=true``): use ``front_photo`` and optionally ``back_photo``.
      Photos are encrypted and stored in the database (max 2 MB each).
    - **Other documents** (``is_id=false``): use the ``file`` field.
      The file is encrypted and stored on the filesystem (no size limit).
    """
    try:
        if is_id:
            front_bytes, front_mime = None, None
            if front_photo:
                if front_photo.content_type not in ALLOWED_PHOTO_MIMES:
                    raise HTTPException(400, "front_photo must be JPEG or PNG")
                front_bytes = await front_photo.read()
                if len(front_bytes) > MAX_ID_PHOTO_SIZE:
                    raise HTTPException(400, "front_photo exceeds 2MB limit for ID storage")
                front_mime = front_photo.content_type

            back_bytes, back_mime = None, None
            if back_photo:
                if back_photo.content_type not in ALLOWED_PHOTO_MIMES:
                    raise HTTPException(400, "back_photo must be JPEG or PNG")
                back_bytes = await back_photo.read()
                if len(back_bytes) > MAX_ID_PHOTO_SIZE:
                    raise HTTPException(400, "back_photo exceeds 2MB limit for ID storage")
                back_mime = back_photo.content_type

            doc = await service.create(
                user_id=user.id,
                client_id=client_id,
                document_type=document_type,
                issue_date=issue_date,
                is_id=True,
                document_number=document_number or None,
                expiry_date=expiry_date,
                document_type_other=document_type_other,
                front_photo=front_bytes,
                front_photo_mime=front_mime,
                back_photo=back_bytes,
                back_photo_mime=back_mime,
            )
        else:
            file_bytes, file_mime = None, None
            if file:
                file_bytes = await file.read()
                file_mime = file.content_type

            doc = await service.create(
                user_id=user.id,
                client_id=client_id,
                document_type=document_type,
                issue_date=issue_date,
                is_id=False,
                document_number=document_number or None,
                expiry_date=expiry_date,
                document_type_other=document_type_other,
                front_photo=file_bytes,
                front_photo_mime=file_mime,
            )
        return DocumentResponse.from_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from None


@crm_router.get("/documents", response_model=PaginatedResponse[DocumentResponse])
@limiter.limit("60/minute")
async def list_documents(
    request: Request,  # noqa: ARG001
    client_id: UUID | None = Query(None),  # noqa: B008
    document_type: str | None = Query(None, max_length=50),  # noqa: B008
    search: str | None = Query(None, max_length=200),  # noqa: B008
    status: str = Query("active"),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    limit: int = Query(100, ge=1, le=500),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> PaginatedResponse[DocumentResponse]:
    """List documents. Requires documents:read permission."""
    include_inactive = status == "all" or status == "inactive"
    docs, total = await service.list_all(
        user.id,
        client_id=client_id,
        document_type=document_type,
        search=search,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[DocumentResponse.from_document(d) for d in docs],
        total=total,
        offset=offset,
        limit=limit,
    )


@crm_router.post("/documents/photos/batch", response_model=DocumentBatchPhotosResponse)
@limiter.limit("30/minute")
async def batch_document_photos(
    body: DocumentBatchPhotosRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> DocumentBatchPhotosResponse:
    """Get front and back photos for up to 50 documents in batch.
    Requires documents:read permission. Missing photos return as null."""
    entries = await service.get_photos_batch(user.id, body.document_ids)
    return DocumentBatchPhotosResponse(photos=[DocumentPhotoEntry(**e) for e in entries])


@crm_router.get("/documents/{document_id}", response_model=DocumentResponse)
@limiter.limit("60/minute")
async def get_document(
    document_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> DocumentResponse:
    """Get a document by ID (metadata only, no photos). Requires documents:read permission."""
    try:
        doc = await service.get(user.id, document_id)
        return DocumentResponse.from_document(doc)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None


@crm_router.get("/documents/{document_id}/photo/front")
@limiter.limit("60/minute")
async def get_document_front_photo(
    document_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
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
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None


@crm_router.get("/documents/{document_id}/photo/back")
@limiter.limit("60/minute")
async def get_document_back_photo(
    document_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
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
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None


@crm_router.patch("/documents/{document_id}", response_model=DocumentResponse)
@limiter.limit("30/minute")
async def update_document(
    document_id: UUID,
    body: DocumentUpdateRequest,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None


@crm_router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_document(
    document_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> None:
    """Soft-delete a document. Requires documents:delete permission."""
    deleted = await service.soft_delete(user.id, document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None


@crm_router.post("/documents/{document_id}/restore", response_model=DocumentResponse)
@limiter.limit("20/minute")
async def restore_document(
    document_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> DocumentResponse:
    """Restore a soft-deleted document. Requires documents:delete permission."""
    doc = await service.restore(user.id, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None
    return DocumentResponse.from_document(doc)


@crm_router.delete("/documents/{document_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def hard_delete_document(
    document_id: UUID,
    request: Request,  # noqa: ARG001
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> None:
    """Permanently delete a soft-deleted document. Requires documents:delete permission."""
    deleted = await service.hard_delete(user.id, document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or still active",
        ) from None
