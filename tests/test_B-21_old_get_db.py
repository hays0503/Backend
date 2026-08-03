"""B-21: No legacy get_db() code.

Regression: no legacy sqlite3.connect() calls in route modules.
Behavioral: all routes use get_db() pattern.
"""
import inspect


class TestNoLegacyConnections:
    """Regression: route files should not contain direct sqlite3.connect() calls."""

    def test_auth_routes_no_direct_connect(self):
        from app.routes import auth_routes
        source = inspect.getsource(auth_routes)
        assert "sqlite3.connect" not in source, (
            "auth_routes.py still contains direct sqlite3.connect() calls"
        )

    def test_sensor_routes_no_direct_connect(self):
        from app.routes import sensor_routes
        source = inspect.getsource(sensor_routes)
        assert "sqlite3.connect" not in source, (
            "sensor_routes.py still contains direct sqlite3.connect() calls"
        )

    def test_admin_routes_no_direct_connect(self):
        from app.routes import admin_routes
        source = inspect.getsource(admin_routes)
        assert "sqlite3.connect" not in source, (
            "admin_routes.py still contains direct sqlite3.connect() calls"
        )

    def test_audit_module_no_direct_connect(self):
        from app import audit
        source = inspect.getsource(audit)
        assert "sqlite3.connect" not in source, (
            "audit.py still contains direct sqlite3.connect() calls"
        )

    def test_sensors_module_no_direct_connect(self):
        from app import sensors
        source = inspect.getsource(sensors)
        assert "sqlite3.connect" not in source, (
            "sensors.py still contains direct sqlite3.connect() calls"
        )


class TestRoutesUseGetDB:
    """Behavioral: all routes should route DB access through get_db().

    Routes delegate to the service layer; the requirement is that no route
    module opens direct sqlite3 connections (checked above) and that the
    request-scoped get_db() factory is used by the modules they call.
    """

    def test_auth_service_imports_get_db(self):
        from app.services import auth_service
        source = inspect.getsource(auth_service)
        assert "get_db" in source, "auth_service should use get_db"

    def test_sensor_service_imports_get_db(self):
        from app.services import sensor_service
        source = inspect.getsource(sensor_service)
        assert "get_db" in source, "sensor_service should use get_db"

    def test_admin_route_imports_get_db(self):
        from app.routes import admin_routes
        source = inspect.getsource(admin_routes)
        assert "get_db" in source, "admin routes should use get_db"
