"""B-10: Request logging (method, path, status, duration).

Regression: each request logs method, path, status, duration.
Behavioral: tokens/secrets are NOT logged.
"""
import logging


class TestRequestLogging:
    """Regression: each request should log method, path, status, duration."""

    def test_request_logs_method(self, app, client, caplog):
        with caplog.at_level(logging.INFO):
            client.get("/api/health")
        log_text = caplog.text.lower()
        assert "get" in log_text or "method" in log_text or "request" in log_text, (
            "Request log should include HTTP method"
        )

    def test_request_logs_path(self, app, client, caplog):
        with caplog.at_level(logging.INFO):
            client.get("/api/health")
        log_text = caplog.text.lower()
        assert "/api/health" in log_text or "path" in log_text, (
            "Request log should include request path"
        )

    def test_request_logs_status(self, app, client, caplog):
        with caplog.at_level(logging.INFO):
            client.get("/api/health")
        log_text = caplog.text.lower()
        assert "200" in log_text or "status" in log_text, (
            "Request log should include status code"
        )

    def test_request_logs_duration(self, app, client, caplog):
        with caplog.at_level(logging.INFO):
            client.get("/api/health")
        log_text = caplog.text.lower()
        assert "ms" in log_text or "duration" in log_text or "time" in log_text or "elapsed" in log_text, (
            "Request log should include duration"
        )


class TestLoggingSecurity:
    """Behavioral: tokens and secrets must NOT appear in logs."""

    def test_tokens_not_in_logs(self, app, client, caplog):
        with caplog.at_level(logging.DEBUG):
            resp = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "Admin123456!"},
            )
        data = resp.get_json()
        access_token = data.get("access_token", "")
        log_text = caplog.text
        if access_token:
            assert access_token not in log_text, (
                "Access token must not appear in log output"
            )

    def test_passwords_not_in_logs(self, app, client, caplog):
        with caplog.at_level(logging.DEBUG):
            client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "Admin123456!"},
            )
        assert "Admin123456!" not in caplog.text, (
            "Password must not appear in log output"
        )

    def test_secret_key_not_in_logs(self, app, client, caplog):
        from app.config import Config
        with caplog.at_level(logging.DEBUG):
            client.get("/api/health")
        assert Config.SECRET_KEY not in caplog.text, (
            "SECRET_KEY must not appear in log output"
        )
