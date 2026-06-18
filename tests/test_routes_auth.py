import pytest


class TestLogin:
    def test_login_success(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"

    def test_login_missing_credentials(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Missing credentials"

    def test_login_wrong_password(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Invalid credentials"

    def test_login_wrong_username(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert resp.status_code == 401

    def test_login_no_json_body(self, client):
        resp = client.post("/api/auth/login", data="not json", content_type="text/plain")
        assert resp.status_code == 400


class TestRefresh:
    def test_refresh_success(self, client):
        login_resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin"}
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_blacklists_old_token(self, client):
        login_resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin"}
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        resp = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert resp.status_code == 401

    def test_refresh_missing_token(self, client):
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 400

    def test_refresh_invalid_token(self, client):
        resp = client.post(
            "/api/auth/refresh", json={"refresh_token": "invalid.jwt.here"}
        )
        assert resp.status_code == 401


class TestAuthMe:
    def test_auth_me_returns_user_profile(self, client, sample_data):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert isinstance(data["controllers"], list)

    def test_auth_me_includes_controller_macs(self, client, sample_data):
        resp = client.get("/api/auth/me")
        data = resp.get_json()
        assert "AA:BB:CC:DD:EE:FF" in data["controllers"]
