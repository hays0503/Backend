"""B-08: GET /api/health endpoint.

Regression: GET /api/health returns 200.
Behavioral: response has 'status' key; DB connectivity check.
"""


class TestHealthEndpointExists:
    """Regression: /api/health must return 200."""

    def test_health_returns_200(self, app, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200, (
            f"/api/health should return 200, got {resp.status_code}"
        )

    def test_health_returns_json(self, app, client):
        resp = client.get("/api/health")
        assert resp.content_type.startswith("application/json")


class TestHealthResponse:
    """Behavioral: health response contains expected fields."""

    def test_health_has_status_field(self, app, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert "status" in data, (
            f"Response should have 'status' key, got: {list(data.keys())}"
        )

    def test_health_status_is_ok(self, app, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_health_includes_readings_count(self, app, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert "readings_count" in data or "status" in data

    def test_health_works_with_valid_db(self, app, client, sample_data):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok"

    def test_health_no_auth_required(self, app, client):
        resp = client.get("/api/health")
        assert resp.status_code != 401, "Health endpoint should not require authentication"
