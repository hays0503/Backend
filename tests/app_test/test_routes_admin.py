def _regular_user_headers(client):
    """Create a regular user and return its auth headers. Black-box."""
    admin_resp = client.post(
        "/api/auth/login", json={"username": "admin", "password": "Admin123456!"}
    )
    admin_token = admin_resp.get_json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    client.post(
        "/api/admin/users",
        json={"username": "regular_user", "password": "pass"},
        headers=admin_headers,
    )
    login = client.post(
        "/api/auth/login",
        json={"username": "regular_user", "password": "pass"},
    )
    token = login.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAdminListUsersBlackBox:
    def test_lists_users(self, client, auth_headers):
        resp = client.get("/api/admin/users", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "users" in body
        assert len(body["users"]) >= 1

    def test_contains_admin_user(self, client, auth_headers):
        resp = client.get("/api/admin/users", headers=auth_headers)
        users = resp.get_json()["users"]
        admin = [u for u in users if u["username"] == "admin"]
        assert len(admin) == 1
        assert admin[0]["role"] == "admin"

    def test_each_user_has_controllers_field(self, client, auth_headers):
        resp = client.get("/api/admin/users", headers=auth_headers)
        for user in resp.get_json()["users"]:
            assert "controllers" in user
            assert isinstance(user["controllers"], list)


class TestAdminCreateUserBlackBox:
    def test_create_user_returns_201_with_id(self, client, auth_headers):
        resp = client.post(
            "/api/admin/users",
            json={"username": "alice", "password": "secret"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["username"] == "alice"
        assert body["role"] == "user"
        assert isinstance(body["id"], int)

    def test_created_user_can_login(self, client, auth_headers):
        client.post(
            "/api/admin/users",
            json={"username": "bob", "password": "bobpass"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/auth/login", json={"username": "bob", "password": "bobpass"}
        )
        assert resp.status_code == 200

    def test_duplicate_username_returns_400(self, client, auth_headers):
        client.post(
            "/api/admin/users",
            json={"username": "dupuser", "password": "x"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/admin/users",
            json={"username": "dupuser", "password": "y"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_missing_fields_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/admin/users", json={"username": "x"}, headers=auth_headers
        )
        assert resp.status_code == 400

    def test_create_is_audited(self, client, auth_headers):
        client.post(
            "/api/admin/users",
            json={"username": "audited_user", "password": "p"},
            headers=auth_headers,
        )
        resp = client.get("/api/admin/audit?limit=50", headers=auth_headers)
        actions = [log["action"] for log in resp.get_json()["logs"]]
        assert "user_created" in actions


class TestAdminDeleteUserBlackBox:
    def test_delete_user_returns_200(self, client, auth_headers):
        resp = client.post(
            "/api/admin/users",
            json={"username": "deleteme", "password": "p"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["id"]

        resp = client.delete(f"/api/admin/users/{user_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_deleted_user_cannot_login(self, client, auth_headers):
        resp = client.post(
            "/api/admin/users",
            json={"username": "goner", "password": "p"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["id"]
        client.delete(f"/api/admin/users/{user_id}", headers=auth_headers)

        resp = client.post(
            "/api/auth/login", json={"username": "goner", "password": "p"}
        )
        assert resp.status_code == 401

    def test_delete_nonexistent_user_returns_404(self, client, auth_headers):
        resp = client.delete("/api/admin/users/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_last_admin_returns_400(self, client, auth_headers):
        resp = client.delete("/api/admin/users/1", headers=auth_headers)
        assert resp.status_code == 400
        err = resp.get_json()["error"]
        msg = err["message"] if isinstance(err, dict) else err
        assert "last admin" in msg.lower()


class TestAdminResetPasswordBlackBox:
    def test_reset_password_allows_new_login(self, client, auth_headers):
        resp = client.post(
            "/api/admin/users",
            json={"username": "resetme", "password": "oldpwd"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["id"]

        client.put(
            f"/api/admin/users/{user_id}/reset-password",
            json={"new_password": "newpwd"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/auth/login", json={"username": "resetme", "password": "newpwd"}
        )
        assert resp.status_code == 200

    def test_old_password_invalid_after_reset(self, client, auth_headers):
        resp = client.post(
            "/api/admin/users",
            json={"username": "resetme2", "password": "oldpwd"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["id"]
        client.put(
            f"/api/admin/users/{user_id}/reset-password",
            json={"new_password": "newpwd"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/auth/login",
            json={"username": "resetme2", "password": "oldpwd"},
        )
        assert resp.status_code == 401

    def test_reset_nonexistent_user_returns_404(self, client, auth_headers):
        resp = client.put(
            "/api/admin/users/99999/reset-password",
            json={"new_password": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestAdminAssignControllersBlackBox:
    def test_assign_controllers_returns_200(self, client, auth_headers):
        resp = client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": ["00:11:22:33:44:55"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_assigned_controllers_appear_in_user_profile(self, client, auth_headers):
        mac = "AA:BB:CC:DD:EE:FF"
        client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": [mac]},
            headers=auth_headers,
        )
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert mac in resp.get_json()["controllers"]

    def test_assign_empty_list_clears_controllers(self, client, sample_data, auth_headers):
        client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": ["AA:BB:CC:DD:EE:FF"]},
            headers=auth_headers,
        )
        client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": []},
            headers=auth_headers,
        )
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.get_json()["controllers"] == []

    def test_assign_missing_field_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/admin/users/1/controllers",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_assign_nonexistent_user_returns_404(self, client, auth_headers):
        resp = client.put(
            "/api/admin/users/99999/controllers",
            json={"controllers": []},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_assign_new_controllers_replace_old_ones(self, client, auth_headers):
        """Assigning controllers replaces previous assignment, does not append."""
        client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": ["00:11:22:33:44:55"]},
            headers=auth_headers,
        )
        client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": ["66:77:88:99:AA:BB"]},
            headers=auth_headers,
        )
        resp = client.get("/api/auth/me", headers=auth_headers)
        controllers = resp.get_json()["controllers"]
        assert "00:11:22:33:44:55" not in controllers
        assert "66:77:88:99:AA:BB" in controllers


class TestAdminListControllersBlackBox:
    def test_list_controllers_returns_list(self, client, sample_data, auth_headers):
        resp = client.get("/api/admin/controllers", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "controllers" in body
        assert len(body["controllers"]) >= 2

    def test_controller_has_expected_fields(self, client, sample_data, auth_headers):
        resp = client.get("/api/admin/controllers", headers=auth_headers)
        ctrl = resp.get_json()["controllers"][0]
        expected = {"mac", "first_seen", "last_seen", "sensor_count", "owner_id", "owner_username"}
        assert set(ctrl.keys()) == expected


class TestAdminAuditBlackBox:
    def test_audit_returns_logs(self, client, auth_headers):
        resp = client.get("/api/admin/audit", headers=auth_headers)
        assert resp.status_code == 200
        assert "logs" in resp.get_json()

    def test_audit_logs_have_required_fields(self, client, auth_headers):
        resp = client.get("/api/admin/audit", headers=auth_headers)
        log = resp.get_json()["logs"][0]
        expected = {"id", "user_id", "username", "action", "target_type", "target_id", "details", "created_at"}
        assert set(log.keys()) == expected

    def test_audit_pagination(self, client, auth_headers):
        resp = client.get("/api/admin/audit?limit=1&offset=0", headers=auth_headers)
        assert len(resp.get_json()["logs"]) == 1


class TestAuthorizationBlackBox:
    def test_regular_user_cannot_list_users(self, client):
        headers = _regular_user_headers(client)
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 403

    def test_regular_user_cannot_create_user(self, client):
        headers = _regular_user_headers(client)
        resp = client.post(
            "/api/admin/users",
            json={"username": "hacker", "password": "x"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_regular_user_cannot_delete_user(self, client):
        headers = _regular_user_headers(client)
        resp = client.delete("/api/admin/users/1", headers=headers)
        assert resp.status_code == 403

    def test_regular_user_cannot_access_audit(self, client):
        headers = _regular_user_headers(client)
        resp = client.get("/api/admin/audit", headers=headers)
        assert resp.status_code == 403

    def test_regular_user_cannot_access_controllers(self, client):
        headers = _regular_user_headers(client)
        resp = client.get("/api/admin/controllers", headers=headers)
        assert resp.status_code == 403


class TestMultiUserMultiController:
    def test_assign_multiple_controllers_to_each_user(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]

        for name, user_id in users.items():
            resp = client.put(
                f"/api/admin/users/{user_id}/controllers",
                json={"controllers": macs[name]},
                headers=auth_headers,
            )
            assert resp.status_code == 200

    def test_list_users_shows_correct_controllers_per_user(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]

        for name, user_id in users.items():
            client.put(
                f"/api/admin/users/{user_id}/controllers",
                json={"controllers": macs[name]},
                headers=auth_headers,
            )

        resp = client.get("/api/admin/users", headers=auth_headers)
        assert resp.status_code == 200
        for user in resp.get_json()["users"]:
            name = user["username"]
            if name in macs:
                assert sorted(user["controllers"]) == sorted(macs[name])

    def test_list_controllers_shows_correct_owner(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]

        for name, user_id in users.items():
            client.put(
                f"/api/admin/users/{user_id}/controllers",
                json={"controllers": macs[name]},
                headers=auth_headers,
            )

        resp = client.get("/api/admin/controllers", headers=auth_headers)
        assert resp.status_code == 200
        ctrl_map = {c["mac"]: c for c in resp.get_json()["controllers"]}

        for name, user_macs in macs.items():
            for mac in user_macs:
                assert mac in ctrl_map, f"MAC {mac} not found"
                assert ctrl_map[mac]["owner_username"] == name

    def test_reassign_controller_between_users(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]
        alice_id = users["alice"]
        bob_id = users["bob"]
        mac_to_move = macs["alice"][0]

        client.put(
            f"/api/admin/users/{alice_id}/controllers",
            json={"controllers": macs["alice"]},
            headers=auth_headers,
        )
        client.put(
            f"/api/admin/users/{bob_id}/controllers",
            json={"controllers": macs["bob"]},
            headers=auth_headers,
        )

        bob_new = macs["bob"] + [mac_to_move]
        client.put(
            f"/api/admin/users/{bob_id}/controllers",
            json={"controllers": bob_new},
            headers=auth_headers,
        )
        client.put(
            f"/api/admin/users/{alice_id}/controllers",
            json={"controllers": [macs["alice"][1]]},
            headers=auth_headers,
        )

        resp_users = client.get("/api/admin/users", headers=auth_headers)
        for u in resp_users.get_json()["users"]:
            if u["username"] == "alice":
                assert mac_to_move not in u["controllers"]
                assert macs["alice"][1] in u["controllers"]
            elif u["username"] == "bob":
                assert mac_to_move in u["controllers"]

    def test_unassign_all_controllers_from_user(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]
        charlie_id = users["charlie"]

        client.put(
            f"/api/admin/users/{charlie_id}/controllers",
            json={"controllers": macs["charlie"]},
            headers=auth_headers,
        )
        client.put(
            f"/api/admin/users/{charlie_id}/controllers",
            json={"controllers": []},
            headers=auth_headers,
        )

        resp = client.get("/api/admin/users", headers=auth_headers)
        for u in resp.get_json()["users"]:
            if u["username"] == "charlie":
                assert u["controllers"] == []

    def test_same_controller_appears_for_last_assigned_user(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]
        alice_id = users["alice"]
        bob_id = users["bob"]
        shared_mac = macs["alice"][0]

        client.put(
            f"/api/admin/users/{alice_id}/controllers",
            json={"controllers": [shared_mac]},
            headers=auth_headers,
        )
        client.put(
            f"/api/admin/users/{bob_id}/controllers",
            json={"controllers": [shared_mac, macs["bob"][0]]},
            headers=auth_headers,
        )

        resp = client.get("/api/admin/users", headers=auth_headers)
        alice_controllers = []
        bob_controllers = []
        for u in resp.get_json()["users"]:
            if u["username"] == "alice":
                alice_controllers = u["controllers"]
            elif u["username"] == "bob":
                bob_controllers = u["controllers"]

        assert shared_mac in bob_controllers
        assert macs["bob"][0] in bob_controllers

    def test_replace_controllers_does_not_append(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]
        alice_id = users["alice"]
        replacement_mac = macs["charlie"][0]

        client.put(
            f"/api/admin/users/{alice_id}/controllers",
            json={"controllers": macs["alice"]},
            headers=auth_headers,
        )
        client.put(
            f"/api/admin/users/{alice_id}/controllers",
            json={"controllers": [replacement_mac]},
            headers=auth_headers,
        )

        resp = client.get("/api/admin/users", headers=auth_headers)
        for u in resp.get_json()["users"]:
            if u["username"] == "alice":
                assert replacement_mac in u["controllers"]
                for old_mac in macs["alice"]:
                    assert old_mac not in u["controllers"]

    def test_admin_user_can_have_controllers(self, client, multi_user_data, auth_headers):
        macs = multi_user_data["macs"]

        resp = client.put(
            "/api/admin/users/1/controllers",
            json={"controllers": [macs["alice"][0]]},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        resp = client.get("/api/auth/me", headers=auth_headers)
        assert macs["alice"][0] in resp.get_json()["controllers"]

    def test_controller_list_total_count_matches(self, client, multi_user_data, auth_headers):
        users = multi_user_data["users"]
        macs = multi_user_data["macs"]

        for name, user_id in users.items():
            client.put(
                f"/api/admin/users/{user_id}/controllers",
                json={"controllers": macs[name]},
                headers=auth_headers,
            )

        resp = client.get("/api/admin/controllers", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 6

        all_macs = [c["mac"] for c in resp.get_json()["controllers"]]
        from tests.conftest import ALL_MULTI_MACS
        for mac in ALL_MULTI_MACS:
            assert mac in all_macs
