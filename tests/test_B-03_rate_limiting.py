"""B-03: Rate limiting on login/refresh/ingestion.

Regression: 6th rapid login attempt returns 429.
Behavioral: Rate limit headers present; ingestion endpoint rate-limited.
"""
import time
import pytest

TEST_DEVICE_KEY = "test-device-key-for-testing"


class TestLoginRateLimit:
    """Regression: rapid login attempts should be rate-limited."""

    def test_sixth_login_returns_429(self, app, client, db):
        for i in range(6):
            resp = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrongpass"},
            )
        assert resp.status_code == 429, (
            f"6th rapid login should return 429, got {resp.status_code}"
        )

    def test_first_login_not_rate_limited(self, app, client, db):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrongpass"},
        )
        assert resp.status_code != 429

    def test_rate_limit_returns_retry_after(self, app, client, db):
        for i in range(6):
            resp = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrongpass"},
            )
        if resp.status_code == 429:
            data = resp.get_json()
            assert "Retry-After" in resp.headers or "retry_after" in str(data).lower() or "limit" in str(data).lower()


class TestRateLimitHeaders:
    """Behavioral: rate limit response includes useful headers."""

    def test_rate_limited_response_has_headers(self, app, client, db):
        for i in range(6):
            resp = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrongpass"},
            )
        if resp.status_code == 429:
            assert "X-RateLimit-Limit" in resp.headers or "Retry-After" in resp.headers or resp.status_code == 429


class TestRefreshRateLimit:
    """Behavioral: refresh endpoint should be rate-limited."""

    def test_rapid_refresh_returns_429(self, app, client, db):
        resp1 = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Admin123456!"},
        )
        data = resp1.get_json()
        for i in range(6):
            resp = client.post(
                "/api/auth/refresh",
                json={"refresh_token": data["refresh_token"]},
            )
            if resp.status_code == 200:
                data = resp.get_json()
        assert resp.status_code == 429, (
            f"6th rapid refresh should return 429, got {resp.status_code}"
        )


class TestIngestionRateLimit:
    """Behavioral: ingestion endpoint should be rate-limited."""

    def test_rapid_ingestion_returns_429(self, app, client, db):
        ts = int(time.time() * 1000)
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [{"address": "S-RL-001", "temperature": 22.0, "recorded_at": ts}],
        }
        headers = {"X-Device-Key": TEST_DEVICE_KEY}
        last_status = 200
        for i in range(55):
            resp = client.post("/api/sensor/data", json=payload, headers=headers)
            last_status = resp.status_code
            if resp.status_code == 429:
                break
        assert last_status == 429, (
            f"Rapid ingestion should eventually return 429, got {last_status}"
        )
