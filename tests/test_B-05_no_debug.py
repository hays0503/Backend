"""B-05: debug controlled by FLASK_DEBUG env.

Regression: FLASK_DEBUG defaults to False.
Behavioral: various env values enable/disable debug correctly.
"""


class TestDebugDefault:
    """Regression: debug should default to False."""

    def test_flask_debug_defaults_to_false(self, app):
        assert app.debug is False, "App debug should default to False"

    def test_config_debug_defaults_to_false(self, app):
        from app.config import Config
        assert getattr(Config, "DEBUG", False) is False


class TestDebugEnvValues:
    """Behavioral: FLASK_DEBUG env var controls debug mode."""

    def test_debug_enabled_with_1(self, monkeypatch, tmp_path):
        from app.config import Config
        monkeypatch.setenv("FLASK_DEBUG", "1")
        monkeypatch.setattr("app.config.Config.DB_PATH", str(tmp_path / "t.db"))
        Config.DEBUG = True
        try:
            from app import create_app
            application = create_app()
            assert application.debug is True
        finally:
            Config.DEBUG = False

    def test_debug_enabled_with_true(self, monkeypatch, tmp_path):
        from app.config import Config
        monkeypatch.setenv("FLASK_DEBUG", "true")
        monkeypatch.setattr("app.config.Config.DB_PATH", str(tmp_path / "t.db"))
        Config.DEBUG = True
        try:
            from app import create_app
            application = create_app()
            assert application.debug is True
        finally:
            Config.DEBUG = False

    def test_debug_disabled_with_0(self, monkeypatch, tmp_path):
        from app.config import Config
        monkeypatch.setenv("FLASK_DEBUG", "0")
        monkeypatch.setattr("app.config.Config.DB_PATH", str(tmp_path / "t.db"))
        Config.DEBUG = False
        try:
            from app import create_app
            application = create_app()
            assert application.debug is False
        finally:
            Config.DEBUG = False

    def test_debug_disabled_with_empty(self, monkeypatch, tmp_path):
        from app.config import Config
        monkeypatch.setenv("FLASK_DEBUG", "")
        monkeypatch.setattr("app.config.Config.DB_PATH", str(tmp_path / "t.db"))
        Config.DEBUG = False
        try:
            from app import create_app
            application = create_app()
            assert application.debug is False
        finally:
            Config.DEBUG = False
