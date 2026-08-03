"""W-01: Cookie-based auth, CSRF, logout (black-box)."""

ADMIN_PASSWORD = "Admin123456!"


class TestLoginCookies:
    def test_login_sets_http_only_cookies(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        set_cookies = resp.headers.getlist("Set-Cookie")
        joined = "\n".join(set_cookies)
        assert "yescada_access=" in joined
        assert "yescada_refresh=" in joined
        assert "HttpOnly" in joined

    def test_access_cookie_is_lax(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        set_cookies = resp.headers.getlist("Set-Cookie")
        access = next(c for c in set_cookies if c.startswith("yescada_access="))
        assert "SameSite=Lax" in access

    def test_refresh_cookie_is_strict_path_limited(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        set_cookies = resp.headers.getlist("Set-Cookie")
        refresh = next(c for c in set_cookies if c.startswith("yescada_refresh="))
        assert "SameSite=Strict" in refresh
        assert "Path=/api/auth" in refresh

    def test_login_sets_csrf_cookie(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        csrf = client.get_cookie("yescada_csrf")
        assert csrf is not None
        assert csrf.value


class TestCookieAuth:
    def test_me_works_via_access_cookie(self, client):
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert login_resp.status_code == 200
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["username"] == "admin"
        assert body["role"] == "admin"

    def test_me_rejects_expired_cookie(self, client):
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        client.set_cookie("yescada_access", "not-a-valid-jwt", path="/")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_refresh_via_refresh_cookie(self, client):
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert login_resp.status_code == 200
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body["access_token"], str)
        assert isinstance(body["refresh_token"], str)


class TestCSRF:
    def test_csrf_token_endpoint_returns_and_sets_cookie(self, client):
        resp = client.get("/api/auth/csrf-token")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["csrf_token"]
        csrf = client.get_cookie("yescada_csrf")
        assert csrf is not None
        assert csrf.value == body["csrf_token"]

    def test_cookie_mutation_without_csrf_returns_403(self, client):
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        resp = client.put(
            "/api/auth/profile",
            json={"current_password": ADMIN_PASSWORD, "username": "csrfuser"},
        )
        assert resp.status_code == 403

    def test_cookie_mutation_with_csrf_succeeds(self, client):
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        csrf = client.get_cookie("yescada_csrf").value
        resp = client.put(
            "/api/auth/profile",
            json={"current_password": ADMIN_PASSWORD, "username": "csrfuser"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200

    def test_bearer_bypasses_csrf(self, client, auth_headers):
        resp = client.put(
            "/api/auth/profile",
            json={"current_password": ADMIN_PASSWORD, "username": "beareruser"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_test_marker_skips_csrf(self, client):
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        resp = client.put(
            "/api/auth/profile",
            json={"current_password": ADMIN_PASSWORD, "username": "markeruser"},
            headers={"X-YESCADA-TEST": "1"},
        )
        assert resp.status_code != 403


class TestLogout:
    def test_logout_returns_204_and_clears_cookies(self, client):
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        csrf = client.get_cookie("yescada_csrf").value
        resp = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 204
        cleared = "\n".join(resp.headers.getlist("Set-Cookie"))
        assert "yescada_access=" in cleared
        assert "yescada_refresh=" in cleared

    def test_logout_revokes_refresh_session(self, client):
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        refresh_token = login_resp.get_json()["refresh_token"]
        csrf = client.get_cookie("yescada_csrf").value
        resp = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 204
        refresh_resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 401

    def test_logout_works_without_valid_access_token(self, client):
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        refresh_token = login_resp.get_json()["refresh_token"]
        csrf = client.get_cookie("yescada_csrf").value
        client.set_cookie("yescada_access", "expired-or-invalid", path="/")
        resp = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 204
        refresh_resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 401
