"""Async email sender using ZeptoMail API."""

import logging
from typing import Any

import httpx

from dhanada.auth.config import AuthConfig

ZEPTOMAIL_ENDPOINT = "https://api.zeptomail.in/v1.1/email"

logger = logging.getLogger(__name__)


class EmailSender:
    """Async email sender via ZeptoMail REST API."""

    def __init__(self, config: AuthConfig) -> None:
        self._api_key = config.zeptomail_api_key
        self._from_address = config.zeptomail_from_email

    async def send(
        self,
        to: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> bool:
        """Send an email via ZeptoMail API.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            text: Plain-text email body.
            html: Optional HTML email body.

        Returns:
            True if sent successfully.
        """
        payload: dict[str, Any] = {
            "from": {"address": self._from_address},
            "to": [{"email_address": {"address": to}}],
            "subject": subject,
            "textbody": text,
        }
        if html:
            payload["htmlbody"] = html

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    ZEPTOMAIL_ENDPOINT,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                        "authorization": self._api_key,
                    },
                    json=payload,
                )
            if resp.is_success:
                logger.info("Email sent to %s: %s", to, subject)
                return True
            logger.error(
                "ZeptoMail API error: %d %s",
                resp.status_code,
                resp.text,
            )
            return False
        except Exception:
            logger.exception("Failed to send email to %s", to)
            return False

    async def send_verification_email(
        self,
        to: str,
        full_name: str,
        verification_url: str,
    ) -> bool:
        """Send an email verification link.

        Args:
            to: Recipient email address.
            full_name: User's full name for personalisation.
            verification_url: Full URL with verification token.

        Returns:
            True if sent successfully.
        """
        subject = "Verify your email address"
        text = (
            f"Hi {full_name},\n\n"
            f"Please verify your email address by clicking the link below:\n\n"
            f"{verification_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you did not create this account, please ignore this email."
        )
        html = (
            f"<p>Hi {full_name},</p>"
            f"<p>Please verify your email address by clicking the link below:</p>"
            f'<p><a href="{verification_url}">{verification_url}</a></p>'
            f"<p>This link expires in 24 hours.</p>"
            f"<p>If you did not create this account, please ignore this email.</p>"
        )
        return await self.send(to=to, subject=subject, text=text, html=html)

    async def send_password_reset_email(
        self,
        to: str,
        full_name: str,
        reset_url: str,
    ) -> bool:
        """Send a password reset link.

        Args:
            to: Recipient email address.
            full_name: User's full name for personalisation.
            reset_url: Full URL with reset token.

        Returns:
            True if sent successfully.
        """
        subject = "Password Reset Request"
        text = (
            f"Hi {full_name},\n\n"
            f"A password reset was requested for your account. "
            f"Click the link below to reset your password:\n\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour.\n\n"
            f"If you did not request this, please ignore this email."
        )
        html = (
            f"<p>Hi {full_name},</p>"
            f"<p>A password reset was requested for your account. "
            f"Click the link below to reset your password:</p>"
            f'<p><a href="{reset_url}">{reset_url}</a></p>'
            f"<p>This link expires in 1 hour.</p>"
            f"<p>If you did not request this, please ignore this email.</p>"
        )
        return await self.send(to=to, subject=subject, text=text, html=html)

    async def send_temporary_password_email(
        self,
        to: str,
        full_name: str,
        temporary_password: str,
    ) -> bool:
        """Send a temporary password to a user.

        Args:
            to: Recipient email address.
            full_name: User's full name for personalisation.
            temporary_password: The temporary password to send.

        Returns:
            True if sent successfully.
        """
        subject = "Your Temporary Password"
        text = (
            f"Hi {full_name},\n\n"
            f"A temporary password has been generated for your "
            f"KNAPS - Dhanada account.\n\n"
            f"Password: {temporary_password}\n\n"
            f"This password expires in 10 minutes.\n"
            f"For security, please log in and change your password immediately.\n\n"
            f"If you did not request this, please contact your administrator.\n\n"
            f"KNAPS - Dhanada Team"
        )
        html = (
            f"<p>Hi {full_name},</p>"
            f"<p>A temporary password has been generated for your "
            f"<strong>KNAPS - Dhanada</strong> account.</p>"
            f'<p style="font-size:1.2em;font-weight:bold;background:#f3f4f6;'
            f'padding:12px;border-radius:6px;text-align:center;'
            f'font-family:monospace;">{temporary_password}</p>'
            f"<p>This password expires in <strong>10 minutes</strong>.</p>"
            f"<p>For security, please log in and change your password immediately.</p>"
            f"<p>If you did not request this, please contact your administrator.</p>"
            f"<p>KNAPS - Dhanada Team</p>"
        )
        return await self.send(to=to, subject=subject, text=text, html=html)

    async def send_welcome_email(
        self,
        to: str,
        full_name: str,
        temporary_password: str,
        verification_url: str,
    ) -> bool:
        """Send a combined welcome email with temporary password and verification link.

        Args:
            to: Recipient email address.
            full_name: User's full name for personalisation.
            temporary_password: The temporary password to send.
            verification_url: Full URL with verification token.

        Returns:
            True if sent successfully.
        """
        subject = "Welcome to KNAPS - Dhanada — Verify & Sign In"
        text = (
            f"Hi {full_name},\n\n"
            f"Welcome to KNAPS - Dhanada! Your account has been created.\n\n"
            f"Temporary password: {temporary_password}\n"
            f"(This password expires in 10 minutes.)\n\n"
            f"Please verify your email address by clicking the link below:\n"
            f"{verification_url}\n"
            f"(This link expires in 24 hours.)\n\n"
            f"For security, please log in and change your password immediately.\n\n"
            f"If you did not request this, please contact your administrator.\n\n"
            f"KNAPS - Dhanada Team"
        )
        html = (
            f"<p>Hi {full_name},</p>"
            f"<p>Welcome to <strong>KNAPS - Dhanada</strong>! "
            f"Your account has been created.</p>"
            f'<p style="font-size:1.2em;font-weight:bold;background:#f3f4f6;'
            f'padding:12px;border-radius:6px;text-align:center;'
            f'font-family:monospace;">{temporary_password}</p>'
            f"<p>This password expires in <strong>10 minutes</strong>.</p>"
            f"<p>Please verify your email address by clicking the link below:</p>"
            f'<p><a href="{verification_url}">{verification_url}</a></p>'
            f"<p>This link expires in <strong>24 hours</strong>.</p>"
            f"<p>For security, please log in and change your password immediately.</p>"
            f"<p>If you did not request this, please contact your administrator.</p>"
            f"<p>KNAPS - Dhanada Team</p>"
        )
        return await self.send(to=to, subject=subject, text=text, html=html)

    async def send_recovery_approval_email(
        self,
        to: str,
        full_name: str,
        approval_url: str,
    ) -> bool:
        """Send a recovery approval request email.

        Sent when a backup code is used to log in. The user must click
        the link to approve setting up a new authenticator.

        Args:
            to: Recipient email address.
            full_name: User's full name for personalisation.
            approval_url: Full URL with recovery approval token.

        Returns:
            True if sent successfully.
        """
        subject = "Account Recovery — Approve or Ignore"
        text = (
            f"Hi {full_name},\n\n"
            f"A backup code was used to attempt logging into your "
            f"KNAPS - Dhanada account.\n\n"
            f"If this was you, click the link below to approve the "
            f"recovery and set up a new authenticator:\n\n"
            f"{approval_url}\n\n"
            f"This link expires in 15 minutes.\n\n"
            f"If this was NOT you, you can safely ignore this email. "
            f"Your account is still protected by your existing "
            f"authenticator app. The backup code that was used has "
            f"been consumed, but your remaining codes are still valid.\n\n"
            f"KNAPS - Dhanada Team"
        )
        html = (
            f"<p>Hi {full_name},</p>"
            f"<p>A backup code was used to attempt logging into your "
            f"KNAPS - Dhanada account.</p>"
            f"<p>If this was you, click the link below to approve the "
            f"recovery and set up a new authenticator:</p>"
            f'<p><a href="{approval_url}">{approval_url}</a></p>'
            f"<p>This link expires in <strong>15 minutes</strong>.</p>"
            f"<p>If this was <strong>NOT</strong> you, you can safely "
            f"ignore this email. Your account is still protected by your "
            f"existing authenticator app. The backup code that was used "
            f"has been consumed, but your remaining codes are still valid.</p>"
            f"<p>KNAPS - Dhanada Team</p>"
        )
        return await self.send(to=to, subject=subject, text=text, html=html)
