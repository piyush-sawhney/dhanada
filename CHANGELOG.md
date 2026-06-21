# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure
- Auth module with user management, TOTP 2FA, RBAC
- Envelope encryption for TOTP secrets
- Stateless JWT with refresh token rotation
- FastAPI integration with dependencies and router
- Alembic migrations for PostgreSQL

## [0.1.0] - 2026-06-21

### Added
- Project initialization
- Core auth module structure
- Configuration management with pydantic-settings
- Database models (User, Role, RolePermission, TOTPSecret, RefreshToken)
- Envelope encryption (AES-256-GCM + KEK)
- Password hashing with Argon2id
- TOTP generation/verification with pyotp
- JWT tokens (HS256) with access/refresh rotation
- Repository pattern with async SQLAlchemy
- Service layer (UserService, RoleService, TOTPService, TokenService)
- AuthManager facade API
- FastAPI router with authentication endpoints
- Permission-based dependency injection
- Pre-commit hooks (ruff, mypy, bandit, detect-secrets)
- GitHub Actions CI pipeline
- Comprehensive test suite structure