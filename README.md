# Dhanada

Business application with user management, authentication, and authorization.

## Structure

```
dhanada/
├── backend/          # FastAPI backend (Python)
│   ├── src/dhanada/
│   │   └── auth/     # Authentication & authorization module
│   ├── migrations/   # Alembic database migrations
│   └── tests/        # Unit & integration tests
├── frontend/         # Frontend application (to be added)
└── ...
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- UV (recommended) or pip

### Installation

```bash
# Clone and enter
cd dhanada

# Install dependencies
make install-dev

# Generate encryption key for TOTP secrets
make generate-kek

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
make upgrade-db

# Start development server
make run
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `DHANADA_AUTH_JWT_SECRET_KEY` | JWT signing key (32+ chars) | Yes |
| `DHANADA_AUTH_KEK_BASE64` | Base64-encoded 32-byte KEK | Yes |
| `DHANADA_AUTH_TOTP_ISSUER` | TOTP issuer name | No (default: "Dhanada") |

Generate KEK:
```bash
make generate-kek
```

## Development

```bash
# Run tests
make test

# Lint
make lint

# Format
make format

# Type check
make typecheck

# Security scans
make security

# Full CI pipeline
make ci
```

## Auth Module (`dhanada.auth`)

### Features

- **User Management**: Registration, authentication, profile
- **Session Management**: Stateless JWT (15min) + rotating refresh tokens (7d)
- **Two-Factor Auth**: TOTP (RFC 6238) with QR code enrollment
- **Backup Codes**: 5 single-use recovery codes
- **RBAC**: Roles with resource/action permissions
- **Envelope Encryption**: TOTP secrets encrypted at rest (AES-256-GCM + KEK)

### API Endpoints

```
POST   /auth/register           # Register new user
POST   /auth/login              # Login (returns access + refresh tokens)
POST   /auth/refresh            # Refresh access token
POST   /auth/logout             # Revoke current session
POST   /auth/logout-all         # Revoke all user sessions

GET    /auth/me                 # Current user profile
PATCH  /auth/me                 # Update profile
POST   /auth/change-password    # Change password

POST   /auth/totp/enable        # Start TOTP enrollment (returns QR)
POST   /auth/totp/verify        # Verify TOTP token
POST   /auth/totp/disable       # Disable TOTP
POST   /auth/totp/backup-codes  # Generate new backup codes

GET    /auth/roles              # List user roles
POST   /auth/roles              # Assign role to user
DELETE /auth/roles/{role_name}  # Revoke role from user
```

### Usage in Code

```python
from dhanada.auth import AuthManager, AuthConfig

config = AuthConfig(
    database_url="postgresql+asyncpg://...",
    jwt_secret_key="your-secret",
    kek_base64="your-base64-kek",
)
auth = AuthManager(config)

# Register user
user = await auth.register_user(
    email="user@example.com",
    username="johndoe",
    password="secure_password",
    full_name="John Doe",
)

# Login with 2FA
tokens = await auth.authenticate(
    email="user@example.com",
    password="secure_password",
    totp_token="123456",  # From authenticator app
)

# Check permission
can_delete = await auth.check_permission(user.id, "users", "delete")
```

## License

MIT