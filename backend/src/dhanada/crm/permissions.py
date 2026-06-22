"""CRM permission definitions."""

PERMISSIONS = {
    "clients:read": "View client list and details (without PAN)",
    "clients:create": "Create new clients",
    "clients:edit": "Edit client name and details",
    "clients:delete": "Soft-delete clients",
    "clients:export": "Export client data as CSV",
    "clients:manage-pan": "View and update encrypted PAN numbers",
    "documents:read": "View document list and details",
    "documents:create": "Upload new documents",
    "documents:edit": "Edit document metadata",
    "documents:delete": "Delete documents",
}
