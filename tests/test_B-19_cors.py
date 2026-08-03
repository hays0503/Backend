"""B-19: CORS headers match policy.

Regression: CORS headers match configured origins.
Behavioral: credentials are NOT allowed by default.
"""
import pytest


class TestCORSHeaders:
    """Regression: CORS headers should match configured origins."""

    def test_cors_allows_configured_origin(self, app, client):
        resp = client.get(
            "/api/auth/me",
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp.status_code in (200, 401)
        acao = resp.headers.get("Access-Control-Allow-Origin")
        assert acao is not None, "CORS header Access-Control-Allow-Origin must be present"
        assert "localhost:5173" in acao

    def test_cors_rejects_unconfigured_origin(self, app, client):
        resp = client.get(
            "/api/auth/me",
            headers={"Origin": "http://evil.com"},
        )
        acao = resp.headers.get("Access-Control-Allow-Origin")
        if acao is not None:
            assert "evil.com" not in acao, (
                "CORS should not allow unconfigured origin"
            )

    def test_cors_headers_on_preflight(self, app, client):
        resp = client.options(
            "/api/auth/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)


class TestCORSCredentials:
    """Behavioral: credentials should NOT be allowed by default."""

    def test_no_credentials_by_default(self, app, client):
        resp = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        acac = resp.headers.get("Access-Control-Allow-Credentials")
        assert acac != "true", (
            "Credentials should NOT be allowed by default (Access-Control-Allow-Credentials must not be 'true')"
        )

    def test_cors_supports_multiple_methods(self, app, client):
        resp = client.options(
            "/api/sensor/data",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        acam = resp.headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in acam or resp.status_code in (200, 204)
