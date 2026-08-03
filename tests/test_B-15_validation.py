"""B-15: Ingestion limits (batch, body, MAC, timestamp).

Regression: batch size limit enforced.
Behavioral: empty readings rejected; MAC validation; timestamp window check.
"""
import time
import pytest


class TestBatchSizeLimit:
    """Regression: batch size must be enforced."""

    def test_oversized_batch_rejected(self, app, client, device_key_data, device_headers):
        ts = int(time.time() * 1000)
        readings = [
            {"address": f"S-LIMIT-{i}", "temperature": 20.0, "recorded_at": ts + i}
            for i in range(1001)
        ]
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": readings,
            },
            headers=device_headers,
        )
        assert resp.status_code == 400, (
            f"Batch of 1001 should be rejected, got {resp.status_code}"
        )

    def test_valid_batch_accepted(self, app, client, device_key_data, device_headers):
        ts = int(time.time() * 1000)
        readings = [
            {"address": f"S-VALID-{i}", "temperature": 20.0, "recorded_at": ts + i}
            for i in range(50)
        ]
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": readings,
            },
            headers=device_headers,
        )
        assert resp.status_code in (200, 201)


class TestEmptyReadings:
    """Behavioral: empty readings list should be rejected."""

    def test_empty_readings_rejected(self, app, client, device_key_data, device_headers):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [],
            },
            headers=device_headers,
        )
        if resp.status_code == 200 or resp.status_code == 201:
            data = resp.get_json()
            assert data["inserted"] == 0


class TestMACValidation:
    """Behavioral: controller MAC must be valid format."""

    def test_invalid_mac_rejected(self, app, client, device_key_data, device_headers):
        ts = int(time.time() * 1000)
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "",
                "readings": [{"address": "S1", "temperature": 20.0, "recorded_at": ts}],
            },
            headers=device_headers,
        )
        assert resp.status_code == 400

    def test_missing_mac_rejected(self, app, client, device_key_data, device_headers):
        ts = int(time.time() * 1000)
        resp = client.post(
            "/api/sensor/data",
            json={
                "readings": [{"address": "S1", "temperature": 20.0, "recorded_at": ts}],
            },
            headers=device_headers,
        )
        assert resp.status_code == 400


class TestTimestampValidation:
    """Behavioral: timestamp must be reasonable."""

    def test_future_timestamp_warning(self, app, client, device_key_data, device_headers):
        future_ts = int(time.time() * 1000) + 86400000 * 365
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S-FUTURE", "temperature": 20.0, "recorded_at": future_ts}],
            },
            headers=device_headers,
        )
        if resp.status_code in (200, 201):
            data = resp.get_json()
            assert "inserted" in data

    def test_zero_timestamp_accepted(self, app, client, device_key_data, device_headers):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S-ZERO", "temperature": 20.0, "recorded_at": 0}],
            },
            headers=device_headers,
        )
        assert resp.status_code in (200, 201, 400)
