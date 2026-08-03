"""B-XX-01: UNIQUE(controller_mac, sensor_address).

Regression: UNIQUE constraint on (controller_mac, sensor_address) enforced.
Behavioral: same sensor_address from different controllers is allowed.
"""
import time
import pytest


class TestSensorUniqueness:
    """Regression: UNIQUE(controller_mac, sensor_address) must be enforced."""

    def test_unique_constraint_on_sensor_address_per_controller(self, app, db):
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
            ("AA:BB:CC:DD:EE:FF", 0, 0, 0),
        )
        db.execute(
            "INSERT INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
            ("SENSOR-UNIQUE-001", "AA:BB:CC:DD:EE:FF", "Room1"),
        )
        db.commit()
        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
                ("SENSOR-UNIQUE-001", "AA:BB:CC:DD:EE:FF", "Room2"),
            )
            db.commit()

    def test_same_address_different_controllers_allowed(self, app, db):
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
            ("AA:BB:CC:DD:EE:FF", 0, 0, 0),
        )
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
            ("11:22:33:44:55:66", 0, 0, 0),
        )
        db.commit()
        db.execute(
            "INSERT INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
            ("SENSOR-MULTI-CTRL", "AA:BB:CC:DD:EE:FF", "Room1"),
        )
        db.execute(
            "INSERT INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
            ("SENSOR-MULTI-CTRL", "11:22:33:44:55:66", "Room2"),
        )
        db.commit()
        count = db.execute(
            "SELECT COUNT(*) FROM sensors WHERE sensor_address = 'SENSOR-MULTI-CTRL'"
        ).fetchone()[0]
        assert count == 2, (
            f"Same sensor_address from different controllers should be allowed, count={count}"
        )

    def test_different_address_same_controller_allowed(self, app, db):
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
            ("AA:BB:CC:DD:EE:FF", 0, 0, 0),
        )
        db.commit()
        db.execute(
            "INSERT INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
            ("SENSOR-A", "AA:BB:CC:DD:EE:FF", "Room1"),
        )
        db.execute(
            "INSERT INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
            ("SENSOR-B", "AA:BB:CC:DD:EE:FF", "Room2"),
        )
        db.commit()
        count = db.execute(
            "SELECT COUNT(*) FROM sensors WHERE controller_mac = 'AA:BB:CC:DD:EE:FF'"
        ).fetchone()[0]
        assert count == 2


class TestSensorUniquenessViaAPI:
    """Behavioral: API should handle duplicate sensor_address gracefully."""

    def test_duplicate_sensor_insert_via_ingestion(self, app, client, device_key_data, device_headers):
        ts = int(time.time() * 1000)
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-DUP-UNIQUE-001", "temperature": 20.0, "recorded_at": ts},
            ],
        }
        resp1 = client.post("/api/sensor/data", json=payload, headers=device_headers)
        assert resp1.status_code in (200, 201)

        payload2 = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-DUP-UNIQUE-001", "temperature": 21.0, "recorded_at": ts + 1},
            ],
        }
        resp2 = client.post("/api/sensor/data", json=payload2, headers=device_headers)
        assert resp2.status_code in (200, 201)

    def test_same_sensor_different_controllers_via_api(self, app, client, device_key_data, device_headers):
        ts = int(time.time() * 1000)
        for mac in ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"]:
            payload = {
                "controller_mac": mac,
                "readings": [
                    {"address": "S-SHARED-ADDR", "temperature": 20.0, "recorded_at": ts},
                ],
            }
            resp = client.post("/api/sensor/data", json=payload, headers=device_headers)
            assert resp.status_code in (200, 201)
