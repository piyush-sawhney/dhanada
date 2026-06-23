"""Security event audit logging service."""

import logging
from typing import Any

audit_logger = logging.getLogger("dhanada.auth.audit")


class AuditService:
    """Security event audit logging.

    Logs security-relevant events via Python's structured logging.
    Events include: login, failed login, password changes, role changes,
    account creation, and admin actions.

    In production, configure a JSON log handler to ship these to
    your centralized logging system (ELK, Datadog, etc.).
    """

    @staticmethod
    def log(
        event: str,
        user_id: str | None = None,
        actor_id: str | None = None,
        ip_address: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Log a security event.

        Args:
            event: Event type name (e.g., "login_success", "login_failure").
            user_id: Target user UUID (the subject of the event).
            actor_id: Acting user UUID (who performed the action).
            ip_address: Client IP address.
            detail: Additional structured data.
        """
        audit_logger.info(
            "Security event: %s",
            event,
            extra={
                "event": event,
                "user_id": user_id,
                "actor_id": actor_id,
                "ip": ip_address,
                "detail": detail or {},
            },
        )

    @staticmethod
    def login_success(
        user_id: str,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log("login_success", user_id=user_id, ip_address=ip_address)

    @staticmethod
    def login_failure(
        email: str,
        ip_address: str | None = None,
        reason: str = "invalid_credentials",
    ) -> None:
        AuditService.log(
            "login_failure",
            detail={"email": email, "reason": reason},
            ip_address=ip_address,
        )

    @staticmethod
    def account_locked(
        user_id: str,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "account_locked",
            user_id=user_id,
            ip_address=ip_address,
        )

    @staticmethod
    def password_changed(
        user_id: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "password_changed",
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )

    @staticmethod
    def user_created(
        user_id: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "user_created",
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )

    @staticmethod
    def role_assigned(
        user_id: str,
        role_name: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "role_assigned",
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
            detail={"role": role_name},
        )

    @staticmethod
    def account_reset(
        user_id: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "account_reset",
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )

    @staticmethod
    def bootstrap_complete(
        user_id: str,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "bootstrap_complete",
            user_id=user_id,
            ip_address=ip_address,
        )

    @staticmethod
    def user_updated(
        user_id: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "user_updated",
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )

    @staticmethod
    def user_deleted(
        user_id: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "user_deleted",
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )

    @staticmethod
    def role_created(
        role_name: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "role_created",
            actor_id=actor_id,
            ip_address=ip_address,
            detail={"role_name": role_name},
        )

    @staticmethod
    def role_deleted(
        role_id: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "role_deleted",
            actor_id=actor_id,
            ip_address=ip_address,
            detail={"role_id": role_id},
        )

    @staticmethod
    def role_updated(
        role_name: str,
        changes: dict | None = None,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "role_updated",
            actor_id=actor_id,
            ip_address=ip_address,
            detail={"role_name": role_name, "changes": changes or {}},
        )

    @staticmethod
    def permission_added(
        role_name: str,
        resource: str,
        action: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "permission_added",
            actor_id=actor_id,
            ip_address=ip_address,
            detail={"role_name": role_name, "resource": resource, "action": action},
        )

    @staticmethod
    def permission_removed(
        role_name: str,
        resource: str,
        action: str,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        AuditService.log(
            "permission_removed",
            actor_id=actor_id,
            ip_address=ip_address,
            detail={"role_name": role_name, "resource": resource, "action": action},
        )
