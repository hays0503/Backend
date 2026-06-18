import pytest


class TestAdminListUsers:
    def test_list_users(self, client, db):
        resp = client.get("/api/admin/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "users" in data
        assert len(data["users"]) == 1
        assert data["users"][0]["username"] == "admin"

    def test_list_users_includes_controllers(self, client, sample_data):
        resp = client.get("/api/admin/users")
        user = resp.get_json()["users"][0]
        assert "controllers" in user


class TestAdminCreateUser:
    def test_create_user_success(self, client, db):
        resp = client.post(
            "/api/admin/users", json={"username": "newuser", "password": "pass123"}
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "newuser"
        assert data["role"] == "user"
        assert data["id"] is not None

    def test_create_user_duplicate_username(self, client, db):
        client.post(
            "/api/admin/users", json={"username": "dup", "password": "pass"}
        )
        resp = client.post(
            "/api/admin/users", json={"username": "dup", "password": "pass"}
        )
        assert resp.status_code == 400

    def test_create_user_missing_fields(self, client):
        resp = client.post("/api/admin/users", json={"username": "x"})
        assert resp.status_code == 400

    def test_create_user_audit_logged(self, client, db):
        client.post(
            "/api/admin/users", json={"username": "audited_user", "password": "pwd"}
        )
        row = db.execute(
            "SELECT action, target_id FROM audit_log WHERE action = ?",
            ("user_created",),
        ).fetchone()
        assert row is not None


class TestAdminDeleteUser:
    def test_delete_user_success(self, client, db):
        client.post(
            "/api/admin/users", json={"username": "todelete", "password": "pass"}
        )
        user_id = db.execute(
            "SELECT id FROM users WHERE username = ?", ("todelete",)
        ).fetchone()[0]

        resp = client.delete(f"/api/admin/users/{user_id}")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_delete_user_not_found(self, client):
        resp = client.delete("/api/admin/users/999")
        assert resp.status_code == 404

    def test_delete_last_admin_blocked(self, client):
        resp = client.delete("/api/admin/users/1")
        assert resp.status_code == 400
        assert "last admin" in resp.get_json()["error"].lower()

    def test_delete_user_clears_controller_links(self, client, db, sample_data):
        client.post(
            "/api/admin/users", json={"username": "deluser", "password": "p"}
        )
        uid = db.execute(
            "SELECT id FROM users WHERE username = ?", ("deluser",)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
            (uid, "AA:BB:CC:DD:EE:FF"),
        )
        db.commit()

        client.delete(f"/api/admin/users/{uid}")
        links = db.execute(
            "SELECT COUNT(*) FROM user_controllers WHERE user_id = ?", (uid,)
        ).fetchone()[0]
        assert links == 0


class TestAdminResetPassword:
    def test_reset_password_success(self, client, db):
        client.post(
            "/api/admin/users", json={"username": "resetme", "password": "oldpwd"}
        )
        uid = db.execute(
            "SELECT id FROM users WHERE username = ?", ("resetme",)
        ).fetchone()[0]

        resp = client.put(
            f"/api/admin/users/{uid}/reset-password",
            json={"new_password": "newpwd"},
        )
        assert resp.status_code == 200

    def test_reset_password_missing_new_password(self, client):
        resp = client.put("/api/admin/users/1/reset-password", json={})
        assert resp.status_code == 400

    def test_reset_password_user_not_found(self, client):
        resp = client.put(
            "/api/admin/users/999/reset-password",
            json={"new_password": "x"},
        )
        assert resp.status_code == 404


class TestAdminAssignControllers:
    def test_assign_controllers_success(self, client, db):
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
            ("CC:DD:EE:FF:00:11", 1000, 1000, 0),
        )
        db.commit()

        resp = client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": ["CC:DD:EE:FF:00:11"]},
        )
        assert resp.status_code == 200

    def test_assign_controllers_replaces_existing(self, client, db, sample_data):
        resp = client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": []},
        )
        assert resp.status_code == 200

        import endpoint
        macs = endpoint.get_user_controller_macs(1)
        assert macs == []

    def test_assign_controllers_missing_field(self, client):
        resp = client.put("/api/admin/users/1/controllers", json={})
        assert resp.status_code == 400

    def test_assign_controllers_user_not_found(self, client):
        resp = client.put(
            "/api/admin/users/999/controllers",
            json={"controllers": []},
        )
        assert resp.status_code == 404


class TestAdminListControllers:
    def test_list_controllers(self, client, sample_data):
        resp = client.get("/api/admin/controllers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "controllers" in data
        assert len(data["controllers"]) >= 1

    def test_list_controllers_includes_owner(self, client, sample_data):
        resp = client.get("/api/admin/controllers")
        ctrl = resp.get_json()["controllers"][0]
        assert "mac" in ctrl
        assert "owner_id" in ctrl
        assert "owner_username" in ctrl
        assert "sensor_count" in ctrl


class TestAdminAudit:
    def test_audit_returns_logs(self, client, db):
        import endpoint
        endpoint.log_action(1, "admin", "test_entry")

        resp = client.get("/api/admin/audit")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "logs" in data
        assert len(data["logs"]) >= 1

    def test_audit_pagination(self, client, db):
        import endpoint
        for i in range(5):
            endpoint.log_action(1, "admin", f"action_{i}")

        resp = client.get("/api/admin/audit?limit=2&offset=0")
        data = resp.get_json()
        assert len(data["logs"]) == 2

    def test_audit_log_fields(self, client, db):
        import endpoint
        endpoint.log_action(1, "admin", "detail_test", "sensor", "42", {"temp": 25})

        resp = client.get("/api/admin/audit?limit=50&offset=0")
        logs = resp.get_json()["logs"]
        log = next(l for l in logs if l["action"] == "detail_test")
        assert log["user_id"] == 1
        assert log["username"] == "admin"
        assert log["target_type"] == "sensor"
        assert log["target_id"] == "42"
        assert log["details"] == {"temp": 25}
