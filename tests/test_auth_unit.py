import jwt
import time
import uuid
import pytest
from flask import g


class TestCreateAccessToken:
    def test_returns_jwt_string(self, app):
        import endpoint
        token = endpoint.create_access_token(1, "admin")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_payload_contains_user_id_and_role(self, app):
        import endpoint
        token = endpoint.create_access_token(42, "user")
        payload = jwt.decode(token, endpoint.SECRET_KEY, algorithms=["HS256"])
        assert payload["user_id"] == 42
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_includes_admin_role(self, app):
        import endpoint
        token = endpoint.create_access_token(1, "admin")
        payload = jwt.decode(token, endpoint.SECRET_KEY, algorithms=["HS256"])
        assert payload["role"] == "admin"


class TestCreateRefreshToken:
    def test_returns_token_and_jti(self, app):
        import endpoint
        token, jti = endpoint.create_refresh_token(1)
        assert isinstance(token, str)
        assert token.count(".") == 2
        assert isinstance(jti, str)
        assert len(jti) > 0

    def test_payload_contains_correct_fields(self, app):
        import endpoint
        token, jti = endpoint.create_refresh_token(42)
        payload = jwt.decode(token, endpoint.SECRET_KEY, algorithms=["HS256"])
        assert payload["user_id"] == 42
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_unique_jti_per_call(self, app):
        import endpoint
        _, jti1 = endpoint.create_refresh_token(1)
        _, jti2 = endpoint.create_refresh_token(1)
        assert jti1 != jti2

    def test_explicit_jti(self, app):
        import endpoint
        fixed_jti = "my-custom-jti-123"
        token, jti = endpoint.create_refresh_token(1, jti=fixed_jti)
        assert jti == fixed_jti
        payload = jwt.decode(token, endpoint.SECRET_KEY, algorithms=["HS256"])
        assert payload["jti"] == fixed_jti


class TestDecodeToken:
    def test_decode_valid_access_token(self, app):
        import endpoint
        token = endpoint.create_access_token(1, "admin")
        payload = endpoint.decode_token(token, "access")
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["role"] == "admin"

    def test_decode_valid_refresh_token(self, app):
        import endpoint
        token, jti = endpoint.create_refresh_token(1)
        payload = endpoint.decode_token(token, "refresh")
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["jti"] == jti

    def test_decode_wrong_type_access_as_refresh(self, app):
        import endpoint
        token = endpoint.create_access_token(1, "admin")
        payload = endpoint.decode_token(token, "refresh")
        assert payload is None

    def test_decode_wrong_type_refresh_as_access(self, app):
        import endpoint
        token, _ = endpoint.create_refresh_token(1)
        payload = endpoint.decode_token(token, "access")
        assert payload is None

    def test_decode_expired_token(self, app):
        import endpoint
        payload = {
            "user_id": 1,
            "role": "user",
            "type": "access",
            "exp": int(time.time()) - 3600,
        }
        token = jwt.encode(payload, endpoint.SECRET_KEY, algorithm="HS256")
        result = endpoint.decode_token(token, "access")
        assert result is None

    def test_decode_wrong_signature(self, app):
        token = jwt.encode(
            {"user_id": 1, "type": "access", "exp": 9999999999},
            "wrong-secret-key",
            algorithm="HS256",
        )
        import endpoint
        result = endpoint.decode_token(token, "access")
        assert result is None

    def test_decode_blacklisted_refresh_token(self, app):
        import endpoint
        token, jti = endpoint.create_refresh_token(1)
        endpoint._blacklist.add(jti)
        payload = endpoint.decode_token(token, "refresh")
        assert payload is None

    def test_decode_non_blacklisted_refresh_token(self, app):
        import endpoint
        token, jti = endpoint.create_refresh_token(1)
        endpoint._blacklist.add("some-other-jti")
        payload = endpoint.decode_token(token, "refresh")
        assert payload is not None

    def test_decode_garbage_string(self, app):
        import endpoint
        result = endpoint.decode_token("not.a.token", "access")
        assert result is None


class TestRequireAdmin:
    def test_allows_admin(self, app):
        import endpoint
        with app.app_context():
            g.user_role = "admin"

            @endpoint.require_admin
            def dummy():
                return "allowed"

            assert dummy() == "allowed"

    def test_denies_user(self, app):
        import endpoint
        with app.app_context():
            g.user_role = "user"

            @endpoint.require_admin
            def dummy():
                return "allowed"

            response = dummy()
            assert response[1] == 403

    def test_denies_no_role(self, app):
        import endpoint
        with app.app_context():
            g.user_role = None

            @endpoint.require_admin
            def dummy():
                return "allowed"

            response = dummy()
            assert response[1] == 403
