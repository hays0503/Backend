"""B-17: Malformed audit JSON doesn't 500.

Regression: malformed JSON in audit log details doesn't cause 500.
Behavioral: graceful handling returns default/empty instead of crash.
"""
import pytest


class TestMalformedAuditJSON:
    """Regression: malformed JSON in audit details must not cause 500."""

    def test_malformed_json_in_audit_log(self, app, db, admin_headers, client):
        db.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "admin", "test_action", "test", "1", "NOT VALID JSON {{{", 1000),
        )
        db.commit()
        resp = client.get("/api/admin/audit", headers=admin_headers)
        assert resp.status_code == 200, (
            f"Malformed JSON in audit details should not cause 500, got {resp.status_code}"
        )

    def test_empty_string_details(self, app, db, admin_headers, client):
        db.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "admin", "test_action2", "test", "2", "", 1000),
        )
        db.commit()
        resp = client.get("/api/admin/audit", headers=admin_headers)
        assert resp.status_code == 200

    def test_none_details(self, app, db, admin_headers, client):
        db.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "admin", "test_action3", "test", "3", None, 1000),
        )
        db.commit()
        resp = client.get("/api/admin/audit", headers=admin_headers)
        assert resp.status_code == 200


class TestAuditJSONGracefulHandling:
    """Behavioral: audit endpoint handles corrupt data gracefully."""

    def test_audit_returns_valid_json_response(self, app, db, admin_headers, client):
        corrupt_entries = [
            "{invalid",
            "[]",
            '{"incomplete":',
            "random text",
            "12345",
        ]
        for i, detail in enumerate(corrupt_entries):
            db.execute(
                "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "admin", f"action_{i}", "test", str(i), detail, 1000 + i),
            )
        db.commit()
        resp = client.get("/api/admin/audit", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "logs" in data

    def test_audit_with_binary_garbage(self, app, db, admin_headers, client):
        db.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "admin", "binary_action", "test", "99", b"\x00\x01\x02\xff".decode("latin-1"), 2000),
        )
        db.commit()
        resp = client.get("/api/admin/audit", headers=admin_headers)
        assert resp.status_code == 200
