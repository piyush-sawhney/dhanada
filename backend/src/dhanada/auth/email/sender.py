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
        username: str,
        verification_url: str,
    ) -> bool:
        """Send an email verification link.

        Args:
            to: Recipient email address.
            username: User's username for personalisation.
            verification_url: Full URL with verification token.

        Returns:
            True if sent successfully.
        """
        subject = "Verify your email address"
        text = (
            f"Hi {username},\n\n"
            f"Please verify your email address by clicking the link below:\n\n"
            f"{verification_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you did not create this account, please ignore this email."
        )
        html = (
            f"<p>Hi {username},</p>"
            f"<p>Please verify your email address by clicking the link below:</p>"
            f'<p><a href="{verification_url}">{verification_url}</a></p>'
            f"<p>This link expires in 24 hours.</p>"
            f"<p>If you did not create this account, please ignore this email.</p>"
        )
        return await self.send(to=to, subject=subject, text=text, html=html)
