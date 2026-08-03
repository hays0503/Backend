"""B-18: Server exceptions logged not exposed.

Regression: exceptions are logged server-side.
Behavioral: stack trace is NOT exposed to client response.
"""
import time
import pytest
from unittest.mock import patch


def _valid_payload():
    return {
        "controller_mac": "AA:BB:CC:DD:EE:FF",
        "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": int(time.time() * 1000)}],
    }


class TestExceptionLogging:
    """Regression: exceptions should be logged server-side."""

    def test_internal_error_returns_500(self, app, client, device_key_data, device_headers):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        with patch("app.db.sqlite3") as mock_sqlite:
            mock_sqlite.connect.side_effect = Exception("DB error")
            resp = client.post(
                "/api/sensor/data",
                json=_valid_payload(),
                headers=device_headers,
            )
        assert resp.status_code == 500


class TestExceptionNotExposed:
    """Behavioral: stack trace must NOT be exposed to client."""

    def test_no_stacktrace_in_response(self, app, client, device_key_data, device_headers):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        with patch("app.db.sqlite3") as mock_sqlite:
            mock_sqlite.connect.side_effect = Exception("DB error")
            resp = client.post(
                "/api/sensor/data",
                json=_valid_payload(),
                headers=device_headers,
            )
        data = resp.get_json()
        response_str = str(data).lower()
        assert "traceback" not in response_str, (
            "Response must not contain stack trace"
        )
        assert "stack" not in response_str, (
            "Response must not contain stack info"
        )

    def test_no_exception_message_in_response(self, app, client, device_key_data, device_headers):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        with patch("app.db.sqlite3") as mock_sqlite:
            mock_sqlite.connect.side_effect = Exception("Internal secret error XYZ")
            resp = client.post(
                "/api/sensor/data",
                json=_valid_payload(),
                headers=device_headers,
            )
        if resp.status_code == 500:
            data = resp.get_json()
            assert "Internal secret error XYZ" not in str(data), (
                "Internal exception message must not be exposed to client"
            )

    def test_error_response_is_standardized(self, app, client, device_key_data, device_headers):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        with patch("app.db.sqlite3") as mock_sqlite:
            mock_sqlite.connect.side_effect = Exception("test")
            resp = client.post(
                "/api/sensor/data",
                json=_valid_payload(),
                headers=device_headers,
            )
        data = resp.get_json()
        assert "error" in data, "Error response should have 'error' key"
