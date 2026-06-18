import jwt
import time
import pytest
from flask import g


class TestCreateAccessToken:
    def test_returns_jwt_string(self, app):
        from app.auth import create_access_token
        token = create_access_token(1, "admin")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_payload_contains_user_id_and_role(self, app):
        from app.auth import create_access_token
        from app.config import Config
        token = create_access_token(42, "user")
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        assert payload["user_id"] == 42
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_includes_admin_role(self, app):
        from app.auth import create_access_token
        from app.config import Config
        token = create_access_token(1, "admin")
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        assert payload["role"] == "admin"


class TestCreateRefreshToken:
    def test_returns_token_and_jti(self, app):
        from app.auth import create_refresh_token
        token, jti = create_refresh_token(1)
        assert isinstance(token, str)
        assert token.count(".") == 2
        assert isinstance(jti, str)
        assert len(jti) > 0

    def test_payload_contains_correct_fields(self, app):
        from app.auth import create_refresh_token
        from app.config import Config
        token, jti = create_refresh_token(42)
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        assert payload["user_id"] == 42
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_unique_jti_per_call(self, app):
        from app.auth import create_refresh_token
        _, jti1 = create_refresh_token(1)
        _, jti2 = create_refresh_token(1)
        assert jti1 != jti2

    def test_explicit_jti(self, app):
        from app.auth import create_refresh_token
        from app.config import Config
        fixed_jti = "my-custom-jti-123"
        token, jti = create_refresh_token(1, jti=fixed_jti)
        assert jti == fixed_jti
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        assert payload["jti"] == fixed_jti


class TestDecodeToken:
    def test_decode_valid_access_token(self, app):
        from app.auth import create_access_token, decode_token
        token = create_access_token(1, "admin")
        payload = decode_token(token, "access")
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["role"] == "admin"

    def test_decode_valid_refresh_token(self, app):
        from app.auth import create_refresh_token, decode_token
        token, jti = create_refresh_token(1)
        payload = decode_token(token, "refresh")
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["jti"] == jti

    def test_decode_wrong_type_access_as_refresh(self, app):
        from app.auth import create_access_token, decode_token
        token = create_access_token(1, "admin")
        payload = decode_token(token, "refresh")
        assert payload is None

    def test_decode_wrong_type_refresh_as_access(self, app):
        from app.auth import create_refresh_token, decode_token
        token, _ = create_refresh_token(1)
        payload = decode_token(token, "access")
        assert payload is None

    def test_decode_expired_token(self, app):
        from app.auth import decode_token
        from app.config import Config
        payload = {
            "user_id": 1,
            "role": "user",
            "type": "access",
            "exp": int(time.time()) - 3600,
        }
        token = jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
        result = decode_token(token, "access")
        assert result is None

    def test_decode_wrong_signature(self, app):
        from app.auth import decode_token
        token = jwt.encode(
            {"user_id": 1, "type": "access", "exp": 9999999999},
            "wrong-secret-key",
            algorithm="HS256",
        )
        result = decode_token(token, "access")
        assert result is None

    def test_decode_blacklisted_refresh_token(self, app):
        from app.auth import create_refresh_token, decode_token, revoke_refresh_token
        token, jti = create_refresh_token(1)
        revoke_refresh_token(jti)
        payload = decode_token(token, "refresh")
        assert payload is None

    def test_decode_non_blacklisted_refresh_token(self, app):
        from app.auth import create_refresh_token, decode_token, revoke_refresh_token
        token, jti = create_refresh_token(1)
        revoke_refresh_token("some-other-jti")
        payload = decode_token(token, "refresh")
        assert payload is not None

    def test_decode_garbage_string(self, app):
        from app.auth import decode_token
        result = decode_token("not.a.token", "access")
        assert result is None

    def test_decode_malformed_token(self, app):
        from app.auth import decode_token
        result = decode_token("", "access")
        assert result is None


class TestRevokeRefreshToken:
    def test_revoked_token_fails_decode(self, app):
        from app.auth import create_refresh_token, decode_token, revoke_refresh_token
        token, jti = create_refresh_token(1)
        revoke_refresh_token(jti)
        assert decode_token(token, "refresh") is None

    def test_revoke_non_existent_jti_does_not_raise(self, app):
        from app.auth import revoke_refresh_token, create_refresh_token, decode_token
        revoke_refresh_token("nonexistent-jti")
        token, jti = create_refresh_token(1)
        payload = decode_token(token, "refresh")
        assert payload is not None


class TestRequireAuth:
    def test_missing_auth_header_returns_401(self, app, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, app, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    def test_empty_bearer_returns_401(self, app, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer "}
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, app, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Basic somehash"}
        )
        assert resp.status_code == 401


class TestRequireAdmin:
    def test_allows_admin(self, app):
        from app.auth import require_admin
        with app.app_context():
            g.user_role = "admin"

            @require_admin
            def dummy():
                return "allowed"

            assert dummy() == "allowed"

    def test_denies_user(self, app):
        from app.auth import require_admin
        with app.app_context():
            g.user_role = "user"

            @require_admin
            def dummy():
                return "allowed"

            response = dummy()
            assert response[1] == 403

    def test_denies_no_role(self, app):
        from app.auth import require_admin
        with app.app_context():
            g.user_role = None

            @require_admin
            def dummy():
                return "allowed"

            response = dummy()
            assert response[1] == 403
