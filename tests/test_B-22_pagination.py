"""B-22: Users/controllers have 'total' in response.

Regression: admin list users/controllers response has 'total' field.
Behavioral: stable ordering by id.
"""


class TestUsersTotalField:
    """Regression: admin list users response must have 'total' field."""

    def test_admin_list_users_has_total(self, app, client, admin_headers, sample_data):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data, (
            f"admin_list_users response should have 'total', got keys: {list(data.keys())}"
        )

    def test_admin_list_users_total_is_integer(self, app, client, admin_headers, sample_data):
        resp = client.get("/api/admin/users", headers=admin_headers)
        data = resp.get_json()
        assert isinstance(data["total"], int)


class TestControllersTotalField:
    """Regression: admin list controllers response must have 'total' field."""

    def test_admin_list_controllers_has_total(self, app, client, admin_headers, sample_data):
        resp = client.get("/api/admin/controllers", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data, (
            f"admin_list_controllers response should have 'total', got keys: {list(data.keys())}"
        )

    def test_admin_list_controllers_total_is_integer(self, app, client, admin_headers, sample_data):
        resp = client.get("/api/admin/controllers", headers=admin_headers)
        data = resp.get_json()
        assert isinstance(data["total"], int)


class TestUserStableOrdering:
    """Behavioral: users should be ordered by id."""

    def test_users_ordered_by_id(self, app, client, admin_headers, db, sample_data):
        db.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
            ("charlie", "hash_c", 3000),
        )
        db.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
            ("alice", "hash_a", 1000),
        )
        db.commit()
        resp = client.get("/api/admin/users", headers=admin_headers)
        data = resp.get_json()
        ids = [u["id"] for u in data["users"]]
        assert ids == sorted(ids), f"Users should be ordered by id, got {ids}"

    def test_controllers_ordered_stably(self, app, client, admin_headers, sample_data):
        resp = client.get("/api/admin/controllers", headers=admin_headers)
        data = resp.get_json()
        assert "total" in data
        assert "controllers" in data


class TestTotalMatchesActualCount:
    """Behavioral: total should match actual count in database."""

    def test_users_total_matches_count(self, app, client, admin_headers, db, sample_data):
        actual_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        resp = client.get("/api/admin/users", headers=admin_headers)
        data = resp.get_json()
        assert data["total"] == actual_count, (
            f"total={data['total']} should match actual={actual_count}"
        )
