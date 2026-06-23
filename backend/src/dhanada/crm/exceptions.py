"""CRM exceptions."""

from dhanada.exceptions import DhanadaError


class CRMError(DhanadaError):
    """Base CRM error."""


class ClientNotFoundError(CRMError):
    """Client not found."""


class DocumentNotFoundError(CRMError):
    """Document not found."""
