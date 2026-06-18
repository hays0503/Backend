import pytest


class TestLoginBlackBox:
    def test_valid_credentials_returns_tokens_and_user(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0
        assert isinstance(body["refresh_token"], str) and len(body["refresh_token"]) > 0
        assert body["user"]["username"] == "admin"
        assert body["user"]["role"] == "admin"
        assert isinstance(body["user"]["id"], int)

    def test_wrong_password_returns_401(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Invalid credentials"

    def test_wrong_username_returns_401(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert resp.status_code == 401

    def test_missing_credentials_returns_400(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_non_json_body_returns_400(self, client):
        resp = client.post(
            "/api/auth/login", data="not json", content_type="text/plain"
        )
        assert resp.status_code == 400


class TestAccessTokenBlackBox:
    def test_valid_token_allows_access_to_protected_endpoint(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200

    def test_missing_token_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    def test_empty_bearer_returns_401(self, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer "}
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Basic somehash"}
        )
        assert resp.status_code == 401

    def test_auth_me_returns_user_profile(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["id"] == 1
        assert body["username"] == "admin"
        assert body["role"] == "admin"


class TestRefreshTokenBlackBox:
    def test_valid_refresh_returns_new_tokens(self, client):
        login_resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin"}
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body["access_token"], str)
        assert isinstance(body["refresh_token"], str)

    def test_used_refresh_token_rejected(self, client):
        login_resp = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin"}
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        resp = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert resp.status_code == 401

    def test_missing_refresh_token_returns_400(self, client):
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 400

    def test_invalid_refresh_token_returns_401(self, client):
        resp = client.post(
            "/api/auth/refresh", json={"refresh_token": "bogus.jwt.here"}
        )
        assert resp.status_code == 401


class TestProfileBlackBox:
    def test_update_username_success(self, client, auth_headers):
        resp = client.put(
            "/api/auth/profile",
            json={"current_password": "admin", "username": "newadmin"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["username"] == "newadmin"
        assert body["id"] == 1

    def test_updated_username_persists(self, client, auth_headers):
        client.put(
            "/api/auth/profile",
            json={"current_password": "admin", "username": "persistadmin"},
            headers=auth_headers,
        )
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.get_json()["username"] == "persistadmin"

    def test_update_password_changes_auth(self, client, auth_headers):
        client.put(
            "/api/auth/profile",
            json={"current_password": "admin", "password": "newpass"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "newpass"},
        )
        assert resp.status_code == 200

    def test_old_password_stops_working_after_change(self, client, auth_headers):
        client.put(
            "/api/auth/profile",
            json={"current_password": "admin", "password": "newpass"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert resp.status_code == 401

    def test_update_with_wrong_password_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/auth/profile",
            json={"current_password": "wrong", "username": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.get_json()["error"].lower()

    def test_update_missing_current_password_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/auth/profile",
            json={"username": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
