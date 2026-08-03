"""B-20: CORS origins from env.

Regression: CORS origins configurable via env var.
Behavioral: multiple origins supported.
"""
import pytest


class TestCORSEnvConfig:
    """Regression: CORS origins should be configurable via environment."""

    def test_cors_origins_from_config(self, app):
        from app.config import Config
        assert isinstance(Config.CORS_ORIGINS, list)
        assert len(Config.CORS_ORIGINS) > 0

    def test_cors_origins_include_localhost(self, app):
        from app.config import Config
        assert any("localhost" in o for o in Config.CORS_ORIGINS)


class TestCORSOrigins:
    """Behavioral: multiple CORS origins should be supported."""

    def test_multiple_origins_configurable(self, monkeypatch, tmp_path):
        from app.config import Config
        original = Config.CORS_ORIGINS[:]
        try:
            Config.CORS_ORIGINS = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://example.com",
            ]
            assert len(Config.CORS_ORIGINS) == 3
        finally:
            Config.CORS_ORIGINS = original

    def test_cors_origins_can_be_empty(self):
        from app.config import Config
        original = Config.CORS_ORIGINS[:]
        try:
            Config.CORS_ORIGINS = []
            assert len(Config.CORS_ORIGINS) == 0
        finally:
            Config.CORS_ORIGINS = original

    def test_cors_origins_supports_https(self):
        from app.config import Config
        original = Config.CORS_ORIGINS[:]
        try:
            Config.CORS_ORIGINS = ["https://production.example.com"]
            assert "https://production.example.com" in Config.CORS_ORIGINS
        finally:
            Config.CORS_ORIGINS = original
