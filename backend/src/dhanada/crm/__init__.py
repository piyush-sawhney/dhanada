"""CRM module — Client and Document management."""

from dhanada.crm.exceptions import ClientNotFoundError, CRMError, DocumentNotFoundError
from dhanada.crm.fastapi.router import crm_router
from dhanada.crm.models import Client, Document, DocumentType
from dhanada.crm.pan import normalize_pan, validate_pan
from dhanada.crm.permissions import PERMISSIONS
from dhanada.crm.services import ClientService, DocumentService

__all__ = [
    "Client",
    "ClientNotFoundError",
    "ClientService",
    "CRMError",
    "crm_router",
    "Document",
    "DocumentNotFoundError",
    "DocumentService",
    "DocumentType",
    "PERMISSIONS",
    "validate_pan",
    "normalize_pan",
]
