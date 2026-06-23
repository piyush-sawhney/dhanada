"""Authentication configuration."""

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    """Authentication configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DHANADA_AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/dhanada",  # type: ignore[assignment]
        description="PostgreSQL connection URL",
    )

    # JWT Configuration
    jwt_secret_key: str = Field(
        description="Secret key for JWT signing (min 32 chars)",
        min_length=32,
    )
    jwt_key_id: str = Field(default="current", description="Key ID for the current JWT signing key")
    jwt_previous_secret_keys: list[str] = Field(
        default_factory=list,
        description="List of previous secret keys for token verification during rotation",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=15, description="Access token lifetime in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token lifetime in days"
    )

    # Envelope Encryption - Key Encryption Key (KEK)
    kek_base64: str = Field(description="Base64-encoded 32-byte KEK for envelope encryption")
    kek_previous_base64_keys: list[str] = Field(
        default_factory=list,
        description="Previous KEKs for decryption during key rotation (oldest first)",
    )

    # PAN HMAC Key
    pan_hmac_key: str = Field(
        description="Secret key for HMAC-SHA256 hashing of PAN numbers (min 16 chars)",
        min_length=16,
    )

    # TOTP Configuration
    totp_issuer: str = Field(default="Dhanada", description="TOTP issuer name")
    totp_window: int = Field(default=1, description="TOTP verification window")

    # Account Lockout
    account_lockout_threshold: int = Field(
        default=5, description="Failed login attempts before lockout"
    )
    account_lockout_minutes: int = Field(default=15, description="Lockout duration in minutes")

    # Session
    session_token_bytes: int = Field(default=32, description="Session token entropy")

    # Email / ZeptoMail
    zeptomail_api_key: str = Field(
        description="ZeptoMail API token (SEND_MAIL_TOKEN)",
    )
    zeptomail_from_email: str = Field(
        default="noreply@dhanada.app",
        description="Verified sender email address in ZeptoMail",
    )
    email_verification_token_ttl_minutes: int = Field(
        default=1440,
        description="Email verification token TTL (24h)",
    )
    base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for email links (verification, password reset)",
    )
    password_reset_token_ttl_minutes: int = Field(
        default=60,
        description="Password reset token TTL in minutes",
    )

    # Document Storage
    document_storage_path: str = Field(
        default="./storage/documents",
        description="Base directory for filesystem document storage",
    )

    # Application
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Log level")

    @property
    def access_token_expire_seconds(self) -> int:
        return self.jwt_access_token_expire_minutes * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.jwt_refresh_token_expire_days * 24 * 60 * 60
