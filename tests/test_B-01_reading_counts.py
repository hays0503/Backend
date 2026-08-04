"""B-01: cursor.rowcount instead of total_changes for reading counts.

Regression: Validates correct inserted/duplicate counts in various scenarios.
Behavioral: Edge cases for reading counting.
"""
import time


class TestReadingCountBug:
    """Regression: total_changes gives wrong counts for duplicate detection."""

    def test_single_insert_vs_duplicate(self, app, client, db, device_key_data):
        ts = int(time.time() * 1000)
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [{"address": "S-COUNT-001", "temperature": 22.0, "recorded_at": ts}],
        }
        headers = {"X-Device-Key": "test-device-key-for-testing"}
        resp1 = client.post("/api/sensor/data", json=payload, headers=headers)
        assert resp1.status_code in (200, 201)
        data1 = resp1.get_json()
        assert data1["inserted"] == 1
        assert data1["duplicates"] == 0

        resp2 = client.post("/api/sensor/data", json=payload, headers=headers)
        assert resp2.status_code in (200, 201)
        data2 = resp2.get_json()
        assert data2["inserted"] == 0, (
            f"Duplicate insert should be counted as 0, got {data2['inserted']}"
        )
        assert data2["duplicates"] == 1, (
            f"Duplicate should be counted as 1, got {data2['duplicates']}"
        )

    def test_batch_mixed_new_and_duplicate(self, app, client, db, device_key_data):
        ts = int(time.time() * 1000)
        headers = {"X-Device-Key": "test-device-key-for-testing"}
        payload1 = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-BATCH-001", "temperature": 20.0, "recorded_at": ts},
                {"address": "S-BATCH-001", "temperature": 20.0, "recorded_at": ts + 1},
                {"address": "S-BATCH-001", "temperature": 20.0, "recorded_at": ts + 2},
            ],
        }
        resp1 = client.post("/api/sensor/data", json=payload1, headers=headers)
        assert resp1.status_code in (200, 201)

        payload2 = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-BATCH-001", "temperature": 21.0, "recorded_at": ts},
                {"address": "S-BATCH-001", "temperature": 21.0, "recorded_at": ts + 1},
                {"address": "S-BATCH-001", "temperature": 21.0, "recorded_at": ts + 3},
            ],
        }
        resp2 = client.post("/api/sensor/data", json=payload2, headers=headers)
        assert resp2.status_code in (200, 201)
        data2 = resp2.get_json()
        assert data2["inserted"] == 1, (
            f"Expected 1 new insert, got {data2['inserted']}"
        )
        assert data2["duplicates"] == 2, (
            f"Expected 2 duplicates, got {data2['duplicates']}"
        )


class TestReadingCountEdgeCases:
    """Behavioral: edge cases for reading counting."""

    def test_empty_readings_batch(self, app, client, device_key_data):
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [],
        }
        headers = {"X-Device-Key": "test-device-key-for-testing"}
        resp = client.post("/api/sensor/data", json=payload, headers=headers)
        assert resp.status_code in (200, 201, 400)
        if resp.status_code in (200, 201):
            data = resp.get_json()
            assert data["inserted"] == 0
            assert data["duplicates"] == 0

    def test_all_duplicates_in_batch(self, app, client, db, device_key_data):
        ts = int(time.time() * 1000)
        headers = {"X-Device-Key": "test-device-key-for-testing"}
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-DUP-001", "temperature": 25.0, "recorded_at": ts},
                {"address": "S-DUP-001", "temperature": 25.0, "recorded_at": ts + 1},
            ],
        }
        client.post("/api/sensor/data", json=payload, headers=headers)
        resp = client.post("/api/sensor/data", json=payload, headers=headers)
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data["inserted"] == 0
        assert data["duplicates"] == 2

    def test_new_readings_across_multiple_sensors(self, app, client, device_key_data):
        ts = int(time.time() * 1000)
        headers = {"X-Device-Key": "test-device-key-for-testing"}
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-MULTI-A", "temperature": 20.0, "recorded_at": ts},
                {"address": "S-MULTI-B", "temperature": 21.0, "recorded_at": ts},
                {"address": "S-MULTI-C", "temperature": 22.0, "recorded_at": ts},
            ],
        }
        resp = client.post("/api/sensor/data", json=payload, headers=headers)
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data["inserted"] == 3
        assert data["duplicates"] == 0
