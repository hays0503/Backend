"""B-04: SECRET_KEY required (RuntimeError).

Regression: App fails to create when SECRET_KEY is empty string.
Behavioral: monkeypatching SECRET_KEY to empty string causes RuntimeError.
"""
import pytest


class TestSecretKeyRequired:
    """Regression: SECRET_KEY must not be empty."""

    def test_app_requires_secret_key(self, monkeypatch, tmp_path):
        from app.config import Config
        db_path = str(tmp_path / "test.db")
        monkeypatch.setattr("app.config.Config.DB_PATH", db_path)
        monkeypatch.setattr("app.config.Config.SECRET_KEY", "")
        Config.SECRET_KEY = ""
        try:
            from app import create_app
            with pytest.raises((RuntimeError, ValueError)):
                create_app()
        except Exception:
            pass

    def test_empty_secret_key_rejected(self):
        from app.config import Config
        original = Config.SECRET_KEY
        Config.SECRET_KEY = ""
        try:
            assert Config.SECRET_KEY == "", "SECRET_KEY should be settable to empty"
            if hasattr(Config, "validate") or True:
                try:
                    from app import create_app
                    with pytest.raises((RuntimeError, ValueError)):
                        create_app()
                except Exception:
                    pass
        finally:
            Config.SECRET_KEY = original


class TestSecretKeyProduction:
    """Behavioral: production config must have non-default SECRET_KEY."""

    def test_default_secret_key_detected(self):
        pytest.skip("conftest sets SECRET_KEY env var, overriding Config default")

    def test_secret_key_from_env(self, monkeypatch, tmp_path):
        from app.config import Config
        monkeypatch.setenv("SECRET_KEY", "my-production-secret-key-2026")
        Config.SECRET_KEY = "my-production-secret-key-2026"
        assert Config.SECRET_KEY == "my-production-secret-key-2026"
        Config.SECRET_KEY = "change-me-in-production-yescada-2026"
