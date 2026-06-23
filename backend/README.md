# Dhanada Backend

FastAPI backend with modular auth (JWT, TOTP 2FA, RBAC) and CRM (clients, documents).

## Architecture

```
backend/
├── src/dhanada/
│   ├── auth/          # Auth module (standalone, reusable)
│   │   ├── api.py     # AuthManager — public facade
│   │   ├── auth/      # JWT, TOTP, password hashing, crypto
│   │   ├── services/  # Business logic
│   │   ├── db/        # Repository pattern + session
│   │   ├── fastapi/   # Router, schemas, dependencies
│   │   └── models/    # SQLAlchemy ORM models
│   ├── crm/           # CRM module (clients, documents)
│   │   ├── services.py
│   │   ├── models.py
│   │   ├── fastapi/   # Router + schemas
│   │   └── storage.py # File storage abstraction
│   └── main.py        # FastAPI app entry point
├── migrations/        # Alembic migrations
├── scripts/           # Utility scripts
└── tests/             # Unit + integration tests
```

## Prerequisites

- Python 3.12+
- PostgreSQL 16+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Quick Start

```bash
# From the project root
make install-dev

# Generate KEK for envelope encryption
make generate-kek

# Set up environment
cp .env.example .env
# Edit .env — at minimum set:
#   DHANADA_AUTH_JWT_SECRET_KEY=<random 32+ chars>
#   DHANADA_AUTH_KEK_BASE64=<from make generate-kek>
#   DHANADA_AUTH_PAN_HMAC_KEY=<random 16+ chars>
#   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dhanada

# Run migrations
make upgrade-db

# Start dev server
make run
```

## Environment Variables

All `DHANADA_AUTH_*` variables are read by `AuthConfig` (pydantic-settings).
`DATABASE_URL` (without prefix) is read by Alembic and test fixtures.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL `postgresql+asyncpg://user:pass@host:5432/db` |
| `DHANADA_AUTH_JWT_SECRET_KEY` | Yes | — | JWT signing key (32+ chars) |
| `DHANADA_AUTH_KEK_BASE64` | Yes | — | Base64 32-byte KEK for envelope encryption |
| `DHANADA_AUTH_PAN_HMAC_KEY` | Yes | — | HMAC-SHA256 key for PAN dedup (16+ chars) |
| `DHANADA_AUTH_ZEPTOMAIL_API_KEY` | Yes | — | ZeptoMail API token |
| `DHANADA_AUTH_JWT_KEY_ID` | No | `current` | Key ID for current signing key |
| `DHANADA_AUTH_JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `DHANADA_AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Access token TTL |
| `DHANADA_AUTH_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token TTL |
| `DHANADA_AUTH_TOTP_ISSUER` | No | `Dhanada` | TOTP issuer name |
| `DHANADA_AUTH_TOTP_WINDOW` | No | `1` | TOTP verification window |
| `DHANADA_AUTH_ACCOUNT_LOCKOUT_THRESHOLD` | No | `5` | Failed attempts before lockout |
| `DHANADA_AUTH_ACCOUNT_LOCKOUT_MINUTES` | No | `15` | Lockout duration |
| `DHANADA_AUTH_ZEPTOMAIL_FROM_EMAIL` | No | `noreply@dhanada.app` | Verified sender |
| `DHANADA_AUTH_EMAIL_VERIFICATION_TOKEN_TTL_MINUTES` | No | `1440` | Verification token TTL (24h) |
| `DHANADA_AUTH_PASSWORD_RESET_TOKEN_TTL_MINUTES` | No | `60` | Reset token TTL |
| `DHANADA_AUTH_BASE_URL` | No | `http://localhost:8000` | Base URL for email links |
| `DHANADA_AUTH_DOCUMENT_STORAGE_PATH` | No | `./storage/documents` | File storage directory |
| `DHANADA_AUTH_ENVIRONMENT` | No | `development` | Environment name |
| `DHANADA_AUTH_LOG_LEVEL` | No | `INFO` | Log level |

## Development

```bash
make test          # Run all tests with coverage
make test-unit     # Unit tests only
make test-integration  # Integration tests only
make lint          # Ruff linter
make format        # Ruff formatter
make typecheck     # mypy
make security      # Bandit + pip-audit + detect-secrets
make ci            # Full pipeline
```

### Testing with PostgreSQL

Integration tests connect to the database specified by `DATABASE_URL`
(default: `postgresql+asyncpg://postgres:postgres@localhost:5432/dhanada_test`).

You can use **testcontainers** (automatically creates a disposable PostgreSQL):

```bash
# The conftest.py checks for TESTCONTAINERS=1 env var
TESTCONTAINERS=1 make test-integration
```

Or run against a local PostgreSQL instance. The test fixtures create and
drop `auth` / `crm` schemas per session.

### Key Generation

```bash
# Generate a KEK (outputs base64)
make generate-kek

# Manually:
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

## Auth Module

### Features

- **User lifecycle**: Register, authenticate, profile update, soft-delete, cleanup
- **JWT sessions**: Short-lived access tokens (15 min) + rotating refresh tokens (7 days)
- **TOTP 2FA**: RFC 6238 with encrypted secrets (AES-256-GCM), QR enrollment, backup codes
- **RBAC**: Roles with resource:action permissions, system role protection
- **Account lockout**: Configurable threshold and duration
- **Password reset**: Single-use JWT tokens, email notification
- **Email verification**: Token-based, configurable TTL
- **Audit logging**: Structured security event logging
- **Rate limiting**: SlowAPI-based, per-endpoint configurable

### API Endpoints

```
# Auth
POST   /api/auth/bootstrap             # First superuser setup
GET    /api/auth/bootstrap/status       # Check if bootstrap needed
POST   /api/auth/register               # Admin creates user
POST   /api/auth/login                  # Email + password login
POST   /api/auth/setup-complete         # First-time password + TOTP setup
POST   /api/auth/refresh                # Rotate refresh token
POST   /api/auth/logout                 # Revoke session
POST   /api/auth/logout-all             # Revoke all sessions
GET    /api/auth/me                     # Current user profile
PATCH  /api/auth/me                     # Update profile
POST   /api/auth/change-password        # Change password
POST   /api/auth/forgot-password        # Request reset
POST   /api/auth/reset-password         # Execute reset
POST   /api/auth/send-verification      # Send email verification
GET    /api/auth/verify-email           # Verify with token

# TOTP
POST   /api/auth/totp/enable            # Start enrollment
POST   /api/auth/totp/verify            # Confirm enrollment
POST   /api/auth/totp/disable           # Disable with code
POST   /api/auth/totp/backup-codes      # Generate new codes

# Sessions
GET    /api/auth/sessions               # List active sessions
GET    /api/auth/admin/users/{id}/sessions  # Admin view

# Roles & Permissions
POST   /api/auth/roles/create           # Create role
GET    /api/auth/roles/all              # List all roles
GET    /api/auth/roles/{name}           # Get role with permissions
POST   /api/auth/roles/{name}/permissions   # Add permission
DELETE /api/auth/roles/{name}/permissions   # Remove permission
POST   /api/auth/roles                  # Assign role to user
GET    /api/auth/roles                  # Get user's roles
DELETE /api/auth/roles                  # Revoke role
DELETE /api/auth/roles/{id}             # Delete role (non-system)
GET    /api/auth/permissions            # My permissions
GET    /api/auth/permissions/check      # Check specific permission

# Admin users
GET    /api/auth/users                  # List users
GET    /api/auth/users/{id}             # Get user
PATCH  /api/auth/users/{id}             # Update user
DELETE /api/auth/users/{id}             # Soft-delete user
POST   /api/auth/admin/users/{id}/reset-auth  # Force password reset

# App membership
POST   /api/auth/admin/apps/register         # Assign user to app
DELETE /api/auth/admin/apps/unregister        # Remove user from app
GET    /api/auth/admin/apps/users/{user_id}   # List user's apps
```

## CRM Module

### Features

- **Client management**: CRUD with encrypted PAN (envelope encryption + HMAC dedup)
- **Document management**: ID documents (photos in DB, encrypted) + other docs (filesystem)
- **PAN security**: AES-256-GCM encryption at rest, HMAC-SHA256 for uniqueness checks
- **CSV export**: With optional PAN column for authorized users
- **Batch photo retrieval**: Up to 50 documents per request

### API Endpoints

```
# Clients
POST   /api/crm/clients                     # Create client
GET    /api/crm/clients                      # List clients
GET    /api/crm/clients/{id}                 # Get client
PATCH  /api/crm/clients/{id}                 # Update client name
DELETE /api/crm/clients/{id}                 # Soft-delete
POST   /api/crm/clients/{id}/restore         # Restore
DELETE /api/crm/clients/{id}/hard            # Permanent delete
GET    /api/crm/clients/{id}/pan             # Get with decrypted PAN
PATCH  /api/crm/clients/{id}/pan             # Update PAN
POST   /api/crm/clients/export               # CSV export

# Documents
POST   /api/crm/documents                    # Upload document
GET    /api/crm/documents                    # List documents
GET    /api/crm/documents/{id}               # Get metadata
PATCH  /api/crm/documents/{id}               # Update metadata
DELETE /api/crm/documents/{id}               # Soft-delete
POST   /api/crm/documents/{id}/restore       # Restore
DELETE /api/crm/documents/{id}/hard          # Permanent delete
GET    /api/crm/documents/{id}/photo/front   # Stream front photo
GET    /api/crm/documents/{id}/photo/back    # Stream back photo
POST   /api/crm/documents/photos/batch       # Batch photo retrieval
```

## License

MIT
