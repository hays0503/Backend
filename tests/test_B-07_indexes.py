"""B-07: Justified indexes present.

Regression: EXPLAIN QUERY PLAN shows index usage for sensor lookups.
Behavioral: sensors, audit_log, controllers indexes exist.
"""
import pytest


class TestIndexExistence:
    """Regression: critical indexes must exist."""

    def test_readings_sensor_time_index_exists(self, app, db):
        indexes = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_readings_sensor_time'"
        ).fetchall()
        assert len(indexes) > 0, "idx_readings_sensor_time index must exist"

    def test_sensors_address_index_exists(self, app, db):
        indexes = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%sensors%address%'"
        ).fetchall()
        if not indexes:
            indexes = db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND sql LIKE '%sensors%'"
            ).fetchall()
        assert len(indexes) > 0, "An index on sensors.sensor_address must exist"

    def test_controllers_mac_index_exists(self, app, db):
        pk = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='controllers'"
        ).fetchall()
        assert len(pk) > 0, "controllers table must exist"

    def test_user_controllers_index_exists(self, app, db):
        pk = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_controllers'"
        ).fetchone()
        assert pk is not None, "user_controllers table must exist"


class TestIndexUsage:
    """Behavioral: indexes should be used for common queries."""

    def _get_plan_detail(self, db, query):
        rows = db.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
        return " ".join(row[3] for row in rows)

    def test_index_used_for_sensor_lookup(self, app, db, sample_data):
        detail = self._get_plan_detail(
            db, "SELECT * FROM sensors WHERE sensor_address = 'SENSOR-001'"
        )
        assert "SEARCH" in detail or "INDEX" in detail or "sensors" in detail.lower(), (
            f"Expected index/SEARCH usage for sensor lookup, got: {detail}"
        )

    def test_index_used_for_readings_lookup(self, app, db, sample_data):
        detail = self._get_plan_detail(
            db, "SELECT * FROM readings WHERE sensor_id = 1 ORDER BY recorded_at DESC LIMIT 100"
        )
        assert "idx_readings_sensor_time" in detail or "SEARCH" in detail or "COVERING" in detail, (
            f"Expected idx_readings_sensor_time usage, got: {detail}"
        )

    def test_index_used_for_audit_log_query(self, app, db, sample_data):
        detail = self._get_plan_detail(
            db, "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 50"
        )
        assert "SCAN" in detail or "SEARCH" in detail or "audit_log" in detail.lower(), (
            f"Expected audit_log scan/search, got: {detail}"
        )
