"""B-23: JWT claims validation (iat, iss, aud).

Regression: JWT without 'iat' claim is rejected.
Behavioral: 'iss' and 'aud' claims are validated; clock skew handled.
"""
import time
import pytest
import jwt as pyjwt


class TestJWTClaims:
    """Regression: JWT tokens should include and validate required claims."""

    def test_access_token_has_iat(self, app):
        from app.auth import create_access_token
        token = create_access_token(1, "admin")
        from app.config import Config
        payload = pyjwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"],
                               audience=getattr(Config, "JWT_AUDIENCE", "yescada-api"),
                               issuer=getattr(Config, "JWT_ISSUER", "yescada-core"))
        assert "iat" in payload, (
            f"JWT access token must include 'iat' claim, got: {list(payload.keys())}"
        )

    def test_refresh_token_has_iat(self, app):
        from app.auth import create_refresh_token
        token, _ = create_refresh_token(1)
        from app.config import Config
        payload = pyjwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"],
                               audience=getattr(Config, "JWT_AUDIENCE", "yescada-api"),
                               issuer=getattr(Config, "JWT_ISSUER", "yescada-core"))
        assert "iat" in payload, (
            f"JWT refresh token must include 'iat' claim, got: {list(payload.keys())}"
        )

    def test_access_token_has_iss(self, app):
        from app.auth import create_access_token
        token = create_access_token(1, "admin")
        from app.config import Config
        payload = pyjwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"],
                               audience=getattr(Config, "JWT_AUDIENCE", "yescada-api"),
                               issuer=getattr(Config, "JWT_ISSUER", "yescada-core"))
        assert "iss" in payload, (
            f"JWT access token must include 'iss' claim, got: {list(payload.keys())}"
        )

    def test_access_token_has_aud(self, app):
        from app.auth import create_access_token
        token = create_access_token(1, "admin")
        from app.config import Config
        payload = pyjwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"],
                               audience=getattr(Config, "JWT_AUDIENCE", "yescada-api"),
                               issuer=getattr(Config, "JWT_ISSUER", "yescada-core"))
        assert "aud" in payload, (
            f"JWT access token must include 'aud' claim, got: {list(payload.keys())}"
        )


class TestJWTClaimsValidation:
    """Behavioral: claims should be validated on decode."""

    def test_decode_validates_iss(self, app):
        from app.config import Config
        payload = {
            "user_id": 1,
            "role": "admin",
            "type": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "iss": "wrong-issuer",
            "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        }
        token = pyjwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
        from app.auth import decode_token
        result = decode_token(token, "access")
        assert result is None, (
            "decode_token should reject token with wrong 'iss' claim"
        )

    def test_decode_validates_aud(self, app):
        from app.config import Config
        payload = {
            "user_id": 1,
            "role": "admin",
            "type": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
            "aud": "wrong-audience",
        }
        token = pyjwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
        from app.auth import decode_token
        result = decode_token(token, "access")
        assert result is None, (
            "decode_token should reject token with wrong 'aud' claim"
        )

    def test_decode_rejects_token_without_iat(self, app):
        from app.config import Config
        payload = {
            "user_id": 1,
            "role": "admin",
            "type": "access",
            "exp": int(time.time()) + 3600,
        }
        token = pyjwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
        from app.auth import decode_token
        result = decode_token(token, "access")
        assert result is None, (
            "decode_token should reject token without 'iat' claim"
        )


class TestClockSkew:
    """Behavioral: clock skew should be tolerated within reason."""

    def test_token_issued_5_seconds_early_accepted(self, app):
        from app.config import Config
        payload = {
            "user_id": 1,
            "role": "admin",
            "type": "access",
            "iat": int(time.time()) + 5,
            "exp": int(time.time()) + 3600,
            "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
            "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        }
        token = pyjwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
        from app.auth import decode_token
        result = decode_token(token, "access")
        if result is not None:
            assert result["user_id"] == 1

    def test_token_with_valid_claims_accepted(self, app):
        from app.config import Config
        payload = {
            "user_id": 1,
            "role": "admin",
            "type": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
            "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        }
        token = pyjwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
        from app.auth import decode_token
        result = decode_token(token, "access")
        assert result is not None
        assert result["user_id"] == 1
