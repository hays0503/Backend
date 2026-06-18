import sqlite3
import json
import time
import pytest
from sqlite3 import OperationalError


class TestGetUserControllerMacs:
    def test_returns_empty_for_user_with_no_controllers(self, app, db):
        import endpoint
        macs = endpoint.get_user_controller_macs(999)
        assert macs == []

    def test_returns_macs_for_user_with_controllers(self, app, db, sample_data):
        import endpoint
        macs = endpoint.get_user_controller_macs(1)
        assert "AA:BB:CC:DD:EE:FF" in macs
        assert len(macs) == 1


class TestCheckSensorAccess:
    def test_returns_sensor_data_when_accessible(self, app, db, sample_data):
        import endpoint
        row = endpoint.check_sensor_access(1, 1)
        assert row is not None
        assert row[0] == 1
        assert row[1] == "SENSOR-001"
        assert row[2] == "Living Room"

    def test_returns_none_when_no_controllers(self, app, db, sample_data):
        import endpoint
        row = endpoint.check_sensor_access(1, 999)
        assert row is None

    def test_returns_none_when_sensor_not_in_user_controllers(self, app, db, sample_data):
        import endpoint
        row = endpoint.check_sensor_access(3, 1)
        assert row is None

    def test_returns_none_for_nonexistent_sensor(self, app, db, sample_data):
        import endpoint
        row = endpoint.check_sensor_access(999, 1)
        assert row is None


class TestLogAction:
    def test_inserts_audit_log_entry(self, app, db):
        import endpoint
        endpoint.log_action(1, "admin", "test_action", "test", "123", {"key": "value"})
        row = db.execute(
            "SELECT user_id, username, action, target_type, target_id, details FROM audit_log ORDER BY id DESC"
        ).fetchone()
        assert row is not None
        assert row["user_id"] == 1
        assert row["username"] == "admin"
        assert row["action"] == "test_action"
        assert row["target_type"] == "test"
        assert row["target_id"] == "123"
        assert json.loads(row["details"]) == {"key": "value"}

    def test_inserts_log_without_details(self, app, db):
        import endpoint
        endpoint.log_action(1, "admin", "simple_action")
        row = db.execute(
            "SELECT action, details FROM audit_log WHERE action = ?", ("simple_action",)
        ).fetchone()
        assert row["details"] is None

    def test_log_includes_timestamp(self, app, db):
        import endpoint
        before = int(time.time() * 1000)
        endpoint.log_action(1, "admin", "timed_action")
        after = int(time.time() * 1000)
        row = db.execute(
            "SELECT created_at FROM audit_log WHERE action = ?", ("timed_action",)
        ).fetchone()
        assert before <= row["created_at"] <= after


class TestAuthProfileClosedConnectionBug:
    def test_auth_profile_crashes_due_to_missing_commit(self, app, client):
        with pytest.raises(OperationalError):
            client.put(
                "/api/auth/profile",
                json={"current_password": "admin", "username": "newadmin"},
            )
