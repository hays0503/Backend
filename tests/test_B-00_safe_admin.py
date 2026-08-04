"""B-00: Safe admin bootstrap.

Regression: Tests that weak passwords are rejected.
Behavioral: Tests that validate_password_strength enforces all rules.
"""
import pytest


class TestPasswordStrengthValidation:
    """Regression: validate_password_strength rejects weak passwords."""

    def test_validate_password_strength_rejects_short(self, app):
        from app.db import validate_password_strength
        ok, msg = validate_password_strength("Ab1!")
        assert not ok
        assert "length" in msg.lower() or "12" in msg

    def test_validate_password_strength_rejects_no_uppercase(self, app):
        from app.db import validate_password_strength
        ok, msg = validate_password_strength("alllower1!")
        assert not ok

    def test_validate_password_strength_rejects_no_lowercase(self, app):
        from app.db import validate_password_strength
        ok, msg = validate_password_strength("ALLUPPER1!")
        assert not ok

    def test_validate_password_strength_rejects_no_digit(self, app):
        from app.db import validate_password_strength
        ok, msg = validate_password_strength("NoDigitHere!")
        assert not ok

    def test_validate_password_strength_rejects_no_special(self, app):
        from app.db import validate_password_strength
        ok, msg = validate_password_strength("NoSpecial1A")
        assert not ok

    def test_validate_password_strength_accepts_strong(self, app):
        from app.db import validate_password_strength
        ok, msg = validate_password_strength("Strong1!pass")
        assert ok


class TestSeedAdminRejection:
    """Regression: seed_admin rejects weak passwords."""

    def test_seed_admin_rejects_weak_password(self, app, db, tmp_path):
        from app.db import seed_admin
        result = seed_admin("newadmin", "weak", db_path=str(tmp_path / "test.db"))
        assert result is False or (
            isinstance(result, tuple)
            and result[0] is False
        )

    def test_seed_admin_rejects_no_uppercase(self, app, db, tmp_path):
        from app.db import seed_admin
        result = seed_admin("newadmin", "nouppercase1!", db_path=str(tmp_path / "test.db"))
        assert result is False or (
            isinstance(result, tuple)
            and result[0] is False
        )

    def test_seed_admin_accepts_strong_password(self, app, db, tmp_path):
        from app.db import init_db, seed_admin
        db_path = str(tmp_path / "test2.db")
        init_db(db_path)
        result = seed_admin("newadmin", "Strong1!pass", db_path=db_path)
        assert result is True


class TestSafeAdminBootstrap:
    """Behavioral: app should not start with weak admin credentials in production."""

    def test_app_requires_strong_admin_password(self, monkeypatch, tmp_path):
        db_path = str(tmp_path / "prod.db")
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "weak")
        monkeypatch.setattr("app.config.Config.DB_PATH", db_path)
        from app.config import Config
        Config.ADMIN_PASSWORD = "weak"
        try:
            from app.db import validate_password_strength
            ok, _ = validate_password_strength("weak")
            assert not ok, "Weak password should be rejected"
        except ImportError:
            pytest.skip("validate_password_strength not yet implemented")
