import json
import time
from app.audit import log_action


class TestLogAction:
    def test_inserts_audit_log_entry(self, db):
        log_action(1, "admin", "test_action", "test", "123", {"key": "value"})
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

    def test_inserts_log_without_details(self, db):
        log_action(1, "admin", "simple_action")
        row = db.execute(
            "SELECT action, details FROM audit_log WHERE action = ?", ("simple_action",)
        ).fetchone()
        assert row["details"] is None

    def test_log_includes_timestamp(self, db):
        before = int(time.time() * 1000)
        log_action(1, "admin", "timed_action")
        after = int(time.time() * 1000)
        row = db.execute(
            "SELECT created_at FROM audit_log WHERE action = ?", ("timed_action",)
        ).fetchone()
        assert before <= row["created_at"] <= after

    def test_log_without_target(self, db):
        log_action(2, "user1", "login")
        row = db.execute(
            "SELECT user_id, username, action, target_type, target_id FROM audit_log WHERE action = ?",
            ("login",),
        ).fetchone()
        assert row["user_id"] == 2
        assert row["username"] == "user1"
        assert row["target_type"] is None
        assert row["target_id"] is None

    def test_log_with_null_details(self, db):
        log_action(1, "admin", "null_detail_action", "controller", "MAC:01", None)
        row = db.execute(
            "SELECT details FROM audit_log WHERE action = ?",
            ("null_detail_action",),
        ).fetchone()
        assert row["details"] is None
