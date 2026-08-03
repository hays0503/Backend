"""B-06: Single JOIN in admin_list_users (no N+1).

Regression: admin_list_users should not call get_user_controller_macs per user.
Behavioral: user without controllers returns empty list; user with N controllers returns all.
"""
import pytest


class TestNPlusOneDetection:
    """Regression: admin_list_users should not make N+1 queries."""

    def test_admin_list_users_uses_single_query(self, app, client, sample_data, admin_headers):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "users" in data
        for user in data["users"]:
            assert "controllers" in user


class TestUserControllerAssignment:
    """Behavioral: users with/without controllers return correct data."""

    def test_user_without_controllers_returns_empty_list(self, app, client, db, sample_data, admin_headers):
        db.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
            ("nouser", "hash", 1000),
        )
        db.commit()
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        nouser = [u for u in data["users"] if u["username"] == "nouser"]
        assert len(nouser) == 1
        assert nouser[0]["controllers"] == []

    def test_user_with_multiple_controllers(self, app, client, db, sample_data, admin_headers):
        db.execute(
            "INSERT INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
            (1, "11:22:33:44:55:66"),
        )
        db.commit()
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        admin_user = [u for u in data["users"] if u["username"] == "admin"]
        assert len(admin_user) == 1
        assert len(admin_user[0]["controllers"]) == 2
        assert "AA:BB:CC:DD:EE:FF" in admin_user[0]["controllers"]
        assert "11:22:33:44:55:66" in admin_user[0]["controllers"]
