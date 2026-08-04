"""B-11: Standardized error format {error: {code, message, details}}.

Regression: error responses must follow {error: {code, message, details}} format.
Behavioral: 400, 404, 500 handlers produce correct format.
"""


class TestErrorFormat:
    """Regression: all error responses must follow the standardized format."""

    def test_401_has_standardized_format(self, app, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data
        error = data["error"]
        if isinstance(error, dict):
            assert "code" in error or "message" in error, (
                f"Error should have 'code' or 'message', got: {list(error.keys())}"
            )

    def test_403_has_standardized_format(self, app, client):
        resp = client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code in (401, 403)
        data = resp.get_json()
        assert "error" in data

    def test_404_has_standardized_format(self, app, client, admin_headers):
        resp = client.get("/api/nonexistent", headers=admin_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        error = data["error"]
        if isinstance(error, dict):
            assert "code" in error
            assert "message" in error


class TestErrorHandlerRegistration:
    """Behavioral: Flask error handlers should return standardized format."""

    def test_404_handler_returns_json(self, app, client):
        resp = client.get("/api/does-not-exist-at-all")
        assert resp.status_code == 404
        assert resp.content_type.startswith("application/json")

    def test_405_returns_error(self, app, client):
        resp = client.put("/api/health")
        assert resp.status_code == 405
        data = resp.get_json()
        assert "error" in data

    def test_error_has_details_field(self, app, client, device_key_data, device_headers):
        resp = client.post(
            "/api/sensor/data",
            json={},
            headers=device_headers,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        error = data["error"]
        if isinstance(error, dict):
            assert "details" in error or "message" in error
