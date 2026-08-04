"""B-14: Shared test fixtures.

Regression: conftest fixtures work correctly.
Behavioral: app fixture creates temp DB, seeds admin, provides client.
"""


class TestAppFixture:
    """Regression: app fixture must create valid Flask app."""

    def test_app_is_flask_instance(self, app):
        from flask import Flask
        assert isinstance(app, Flask)

    def test_app_is_testing(self, app):
        assert app.config["TESTING"] is True

    def test_app_has_config(self, app):
        assert hasattr(app.config, "SECRET_KEY") or "SECRET_KEY" in app.config

    def test_app_has_blueprints(self, app):
        assert "auth" in app.blueprints
        assert "sensor" in app.blueprints
        assert "admin" in app.blueprints


class TestClientFixture:
    """Regression: client fixture must provide test client."""

    def test_client_is_flask_test_client(self, app, client):
        from flask.testing import FlaskClient
        assert isinstance(client, FlaskClient)

    def test_client_can_make_requests(self, app, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code in (200, 401)


class TestDBFixture:
    """Regression: db fixture must provide sqlite3 connection."""

    def test_db_is_connection(self, app, db):
        import sqlite3
        assert isinstance(db, sqlite3.Connection)

    def test_db_has_row_factory(self, app, db):
        assert db.row_factory is not None

    def test_db_has_foreign_keys_on(self, app, db):
        fk = db.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1


class TestSampleDataFixture:
    """Behavioral: sample_data fixture populates test data."""

    def test_sample_data_has_controllers(self, app, db, sample_data):
        count = db.execute("SELECT COUNT(*) FROM controllers").fetchone()[0]
        assert count >= 2

    def test_sample_data_has_sensors(self, app, db, sample_data):
        count = db.execute("SELECT COUNT(*) FROM sensors").fetchone()[0]
        assert count >= 3

    def test_sample_data_has_readings(self, app, db, sample_data):
        count = db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        assert count >= 3

    def test_sample_data_has_user_controllers(self, app, db, sample_data):
        count = db.execute("SELECT COUNT(*) FROM user_controllers").fetchone()[0]
        assert count >= 1

    def test_sample_data_returns_correct_ids(self, sample_data):
        assert sample_data["controller_1"] == "AA:BB:CC:DD:EE:FF"
        assert sample_data["controller_2"] == "11:22:33:44:55:66"
        assert sample_data["sensor_1_id"] == 1


class TestAdminSeeding:
    """Behavioral: app fixture seeds admin correctly."""

    def test_admin_user_exists(self, app, db):
        row = db.execute(
            "SELECT username, role FROM users WHERE username = 'admin'"
        ).fetchone()
        assert row is not None
        assert row["role"] == "admin"

    def test_admin_can_login(self, app, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Admin123456!"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
