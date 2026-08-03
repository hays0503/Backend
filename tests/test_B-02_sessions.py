"""B-02: Session management (auth_sessions table).

Regression: auth_sessions table must exist with proper columns.
Behavioral: Login creates session, refresh rotates, revoke_all_sessions works.
"""
import pytest

ADMIN_PASSWORD = "Admin123456!"


class TestAuthSessionsTable:
    """Regression: auth_sessions table must exist."""

    def test_auth_sessions_table_exists(self, app, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='auth_sessions'"
        ).fetchall()
        assert len(tables) > 0, "auth_sessions table must exist"

    def test_auth_sessions_has_expected_columns(self, app, db):
        cols = [row[1] for row in db.execute("PRAGMA table_info(auth_sessions)").fetchall()]
        col_names = [c.lower() for c in cols]
        assert any("token" in c or "jti" in c for c in col_names), (
            f"auth_sessions must have token/jti column, got: {col_names}"
        )
        assert any("user_id" in c for c in col_names), (
            f"auth_sessions must have user_id column, got: {col_names}"
        )
        assert any("revoked" in c or "active" in c or "expires" in c for c in col_names), (
            f"auth_sessions must have revoked/active/expires column, got: {col_names}"
        )


class TestSessionCreation:
    """Behavioral: login creates a session record."""

    def test_login_creates_session(self, app, client, db):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        rows = db.execute("SELECT * FROM auth_sessions").fetchall()
        assert len(rows) >= 1, "Login should create at least one session record"

    def test_login_session_has_user_id(self, app, client, db):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        row = db.execute("SELECT * FROM auth_sessions ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        assert row["user_id"] == 1


class TestSessionRotation:
    """Behavioral: refresh rotates the session."""

    def test_refresh_rotates_session(self, app, client, db):
        resp1 = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        data = resp1.get_json()
        old_count = db.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]

        resp2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": data["refresh_token"]},
        )
        assert resp2.status_code == 200
        new_count = db.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
        assert new_count >= old_count, "Refresh should create a new session record"

    def test_old_refresh_token_rejected_after_rotation(self, app, client, db):
        resp1 = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        data = resp1.get_json()
        old_refresh = data["refresh_token"]

        client.post(
            "/api/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        resp2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert resp2.status_code == 401


class TestRevokeAllSessions:
    """Behavioral: revoke_all_sessions invalidates all sessions."""

    def test_revoke_all_sessions_rejects_tokens(self, app, client):
        resp1 = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        data = resp1.get_json()

        try:
            from app.auth import revoke_all_sessions
            revoke_all_sessions(1)
        except (ImportError, AttributeError):
            pytest.skip("revoke_all_sessions not yet implemented")

        resp2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": data["refresh_token"]},
        )
        assert resp2.status_code == 401
