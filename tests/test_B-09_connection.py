"""B-09: Request-scoped connection via get_db().

Regression: get_db() returns same connection within a request.
Behavioral: foreign_keys=ON on request-scoped connection.
"""


class TestRequestScopedConnection:
    """Regression: get_db() must return the same connection within a request."""

    def test_get_db_returns_same_connection(self, app, db):
        from flask import g

        from app.db import get_db
        with app.app_context():
            g.pop("db", None)
            conn1 = get_db()
            conn2 = get_db()
            assert conn1 is conn2, "get_db() should return the same connection"

    def test_get_db_sets_row_factory(self, app, db):
        from flask import g

        from app.db import get_db
        with app.app_context():
            g.pop("db", None)
            conn = get_db()
            assert conn.row_factory is not None, "Connection should have row_factory set"

    def test_get_db_connection_has_foreign_keys(self, app, db):
        from flask import g

        from app.db import get_db
        with app.app_context():
            g.pop("db", None)
            conn = get_db()
            fk = conn.execute("PRAGMA foreign_keys").fetchone()
            assert fk[0] == 1, "foreign_keys should be ON for request-scoped connection"

    def test_close_db_works(self, app, db):
        from flask import g

        from app.db import close_db, get_db
        with app.app_context():
            g.pop("db", None)
            conn = get_db()
            close_db()
            assert "db" not in g, "close_db should remove db from g"


class TestNoLegacyConnections:
    """Behavioral: routes should not open independent sqlite3.connect() calls.

    DB access flows through the service layer, which uses the request-scoped
    get_db() factory; no route module opens its own connections.
    """

    def test_auth_routes_use_get_db(self):
        import inspect

        from app.routes import auth_routes
        source = inspect.getsource(auth_routes)
        assert "sqlite3.connect" not in source, (
            "auth_routes.py still contains direct sqlite3.connect() calls"
        )
        from app.services import auth_service
        svc_source = inspect.getsource(auth_service)
        assert "get_db" in svc_source, (
            "auth_service should route DB access through get_db()"
        )

    def test_sensor_routes_use_get_db(self):
        import inspect

        from app.routes import sensor_routes
        source = inspect.getsource(sensor_routes)
        assert "sqlite3.connect" not in source, (
            "sensor_routes.py still contains direct sqlite3.connect() calls"
        )
        from app.services import sensor_service
        svc_source = inspect.getsource(sensor_service)
        assert "get_db" in svc_source, (
            "sensor_service should route DB access through get_db()"
        )

    def test_admin_routes_use_get_db(self):
        import inspect

        from app.routes import admin_routes
        source = inspect.getsource(admin_routes)
        assert "sqlite3.connect" not in source, (
            "admin_routes.py still contains direct sqlite3.connect() calls"
        )
        assert "get_db" in source, (
            "admin_routes.py should route DB access through get_db()"
        )

    def test_fk_violation_rolls_back_transaction(self, app, client, sample_data):
        """Contract: FK violation must roll back the transaction."""

        from app.db import get_db
        with app.app_context():
            conn = get_db()
            before = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            try:
                conn.execute(
                    "INSERT INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
                    (99999, 20.0, 1234567890),
                )
            except Exception:
                conn.rollback()
            after = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            assert before == after, (
                f"FK violation should roll back: before={before}, after={after}"
            )
