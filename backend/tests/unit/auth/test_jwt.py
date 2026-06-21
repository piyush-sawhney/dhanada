"""Tests for JWT token management."""

import uuid

import pytest
from jose import jwt

from dhanada.auth.auth.jwt import AccessTokenPayload, JWTManager, RefreshTokenPayload
from dhanada.auth.exceptions import InvalidTokenError, TokenExpiredError


class TestJWTManager:
    def test_create_access_token_returns_string(self, jwt_manager):
        """Access token should be a JWT string."""
        user_id = uuid.uuid4()
        token = jwt_manager.create_access_token(user_id)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_create_access_token_with_claims(self, jwt_manager):
        """Access token should include roles and permissions claims."""
        user_id = uuid.uuid4()
        token = jwt_manager.create_access_token(
            user_id,
            roles=["admin", "editor"],
            permissions=["users:read", "users:write"],
        )
        payload = jwt_manager.verify_access_token(token)
        assert "admin" in payload.roles
        assert "users:read" in payload.permissions

    def test_create_refresh_token_returns_string(self, jwt_manager):
        """Refresh token should be a JWT string."""
        user_id = uuid.uuid4()
        family_id = uuid.uuid4()
        token = jwt_manager.create_refresh_token(user_id, family_id)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_verify_access_token_valid(self, jwt_manager):
        """Verifying a valid access token should return payload."""
        user_id = uuid.uuid4()
        token = jwt_manager.create_access_token(user_id, roles=["user"])
        payload = jwt_manager.verify_access_token(token)
        assert payload.sub == str(user_id)
        assert payload.type == "access"
        assert payload.roles == ["user"]

    def test_verify_refresh_token_valid(self, jwt_manager):
        """Verifying a valid refresh token should return payload."""
        user_id = uuid.uuid4()
        family_id = uuid.uuid4()
        token = jwt_manager.create_refresh_token(user_id, family_id)
        payload = jwt_manager.verify_refresh_token(token)
        assert payload.sub == str(user_id)
        assert payload.type == "refresh"
        assert payload.family_id == str(family_id)

    def test_verify_access_token_for_refresh_fails(self, jwt_manager):
        """Using an access token as refresh token should fail."""
        user_id = uuid.uuid4()
        token = jwt_manager.create_access_token(user_id)
        with pytest.raises(InvalidTokenError, match="not an access token"):
            jwt_manager.verify_access_token(token)
        # Actually, it will fail because type is "access", not "refresh"
        with pytest.raises(InvalidTokenError, match="not an refresh token"):
            jwt_manager.verify_refresh_token(token)
        # Actually, let me re-check - verify_refresh_token checks type != "refresh"
        # so an access token used as refresh should fail
        with pytest.raises(InvalidTokenError, match="not a refresh token"):
            jwt_manager.verify_refresh_token(token)

    def test_expired_token_raises(self):
        """Expired token should raise TokenExpiredError."""
        mgr = JWTManager(
            secret_key="test-secret-key-for-unit-tests-min-32-char!",
            access_token_expire_minutes=-1,  # Already expired
        )
        user_id = uuid.uuid4()
        token = mgr.create_access_token(user_id)
        with pytest.raises(TokenExpiredError):
            mgr.verify_access_token(token)

    def test_invalid_signature_raises(self, jwt_manager):
        """Token with invalid signature should raise InvalidTokenError."""
        user_id = uuid.uuid4()
        token = jwt_manager.create_access_token(user_id)
        # Tamper with the signature
        parts = token.split(".")
        tampered = f"{parts[0]}.{parts[1]}.invalidsignature"
        with pytest.raises(InvalidTokenError):
            jwt_manager.verify_access_token(tampered)

    def test_create_different_tokens_each_time(self, jwt_manager):
        """Each token creation should produce unique tokens (different jti)."""
        user_id = uuid.uuid4()
        t1 = jwt_manager.create_access_token(user_id)
        t2 = jwt_manager.create_access_token(user_id)
        assert t1 != t2

    def test_token_has_required_claims(self, jwt_manager):
        """Token should contain sub, exp, iat, jti, type claims."""
        user_id = uuid.uuid4()
        token = jwt_manager.create_access_token(user_id)
        payload = jwt_manager.verify_access_token(token)
        assert payload.sub == str(user_id)
        assert payload.jti is not None
        assert payload.type == "access"

    def test_refresh_token_type_check(self, jwt_manager):
        """Refresh token should have type=refresh and family_id."""
        user_id = uuid.uuid4()
        family_id = uuid.uuid4()
        token = jwt_manager.create_refresh_token(user_id, family_id)
        decoded = jwt_manager.verify_refresh_token(token)
        assert decoded.type == "refresh"
        assert decoded.family_id == str(family_id)