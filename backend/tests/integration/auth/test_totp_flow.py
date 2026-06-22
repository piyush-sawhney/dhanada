"""Integration tests for TOTP 2FA flows."""

import pytest
from httpx import AsyncClient

from dhanada.auth.api import AuthManager

pytestmark = pytest.mark.asyncio


class TestTOTPFlow:
    """Tests for TOTP enable/verify/disable/backup-codes flows."""

    TOTP_EMAIL = "totp-test@test.com"
    TOTP_USERNAME = "totptest"
    TOTP_PASSWORD = "TotpPass123!"  # noqa: S105

    @pytest.fixture(autouse=True)
    async def setup_totp_user(
        self, auth_manager: AuthManager, superuser_token: str, client: AsyncClient  # noqa: ARG002
    ):
        """Create an active user for TOTP testing."""
        resp = await client.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={
                "email": self.TOTP_EMAIL,
                "username": self.TOTP_USERNAME,
                "full_name": "TOTP Test User",
            },
        )
        assert resp.status_code == 201

        login_resp = await client.post(
            "/api/auth/login",
            json={"email": self.TOTP_EMAIL, "password": self.TOTP_PASSWORD},
        )
        data = login_resp.json()
        self._setup_token = data["setup_token"]

        totp_resp = await client.post(
            "/api/auth/totp/enable",
            headers={"Authorization": f"Bearer {self._setup_token}"},
        )
        self._totp_data = totp_resp.json()

    async def test_enable_totp_returns_secret(self, client: AsyncClient):  # noqa: ARG002
        """POST /totp/enable should return secret and provisioning URI."""
        assert "secret" in self._totp_data
        assert "provisioning_uri" in self._totp_data
        assert self._totp_data["secret"] is not None

    async def test_verify_totp_with_valid_code(
        self, client: AsyncClient
    ):
        """POST /totp/verify should confirm TOTP enrollment."""
        import pyotp

        totp = pyotp.TOTP(self._totp_data["secret"])
        valid_code = totp.now()

        resp = await client.post(
            "/api/auth/totp/verify",
            headers={"Authorization": f"Bearer {self._setup_token}"},
            json={"token": valid_code},
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is True

    async def test_disable_totp_with_invalid_code(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /totp/disable with invalid code should return 400."""
        resp = await client.post(
            "/api/auth/totp/disable",
            headers={"Authorization": f"Bearer {superuser_token}"},
            json={"token": "000000"},
        )
        assert resp.status_code == 400

    async def test_generate_backup_codes(
        self, client: AsyncClient, superuser_token: str
    ):
        """POST /totp/backup-codes should return backup codes."""
        resp = await client.post(
            "/api/auth/totp/backup-codes",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "backup_codes" in data
        assert len(data["backup_codes"]) > 0
