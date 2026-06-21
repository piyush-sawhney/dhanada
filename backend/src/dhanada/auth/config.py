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
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/dhanada",
        description="PostgreSQL connection URL",
    )

    # JWT Configuration
    jwt_secret_key: str = Field(
        description="Secret key for JWT signing (min 32 chars)",
        min_length=32,
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=15, description="Access token lifetime in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token lifetime in days"
    )

    # Envelope Encryption - Key Encryption Key (KEK)
    kek_base64: str = Field(
        description="Base64-encoded 32-byte KEK for envelope encryption"
    )

    # TOTP Configuration
    totp_issuer: str = Field(default="Dhanada", description="TOTP issuer name")
    totp_window: int = Field(default=1, description="TOTP verification window")

    # Password Hashing
    bcrypt_rounds: int = Field(default=12, description="Bcrypt rounds")

    # Session
    session_token_bytes: int = Field(default=32, description="Session token entropy")

    # Application
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Log level")

    @property
    def access_token_expire_seconds(self) -> int:
        return self.jwt_access_token_expire_minutes * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.jwt_refresh_token_expire_days * 24 * 60 * 60