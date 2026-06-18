import pytest


POST_DATA = {
    "controller_mac": "AA:BB:CC:DD:EE:FF",
    "readings": [
        {"address": "SENSOR-001", "temperature": 25.5, "recorded_at": 1000000},
    ],
}


class TestPostSensorData:
    def test_insert_readings_success(self, client, db):
        resp = client.post("/api/sensor/data", json=POST_DATA)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["inserted"] == 1
        assert data["duplicates"] == 0
        assert "server_time" in data

    def test_multiple_readings_inserted(self, client, db):
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-ALPHA", "temperature": 20.0, "recorded_at": 2000000},
                {"address": "S-BETA", "temperature": 21.0, "recorded_at": 2000001},
                {"address": "S-GAMMA", "temperature": 22.0, "recorded_at": 2000002},
            ],
        }
        resp = client.post("/api/sensor/data", json=payload)
        assert resp.status_code == 201
        assert resp.get_json()["inserted"] == 3

    def test_duplicate_readings_are_not_stored(self, client, db):
        client.post("/api/sensor/data", json=POST_DATA)
        resp = client.post("/api/sensor/data", json=POST_DATA)
        assert resp.status_code == 201

        count = db.execute(
            "SELECT COUNT(*) FROM readings"
        ).fetchone()[0]
        assert count == 1

    def test_invalid_readings_format(self, client):
        resp = client.post("/api/sensor/data", json={"controller_mac": "X"})
        assert resp.status_code == 400

    def test_missing_controller_mac(self, client):
        resp = client.post(
            "/api/sensor/data", json={"readings": [{"address": "X", "temperature": 1.0, "recorded_at": 1}]}
        )
        assert resp.status_code == 400

    def test_upserts_controller(self, client, db):
        client.post("/api/sensor/data", json=POST_DATA)
        row = db.execute(
            "SELECT mac, sensor_count FROM controllers WHERE mac = ?",
            ("AA:BB:CC:DD:EE:FF",),
        ).fetchone()
        assert row is not None
        assert row["sensor_count"] == 1

    def test_partial_readings_skip_invalid(self, client, db):
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-VALID", "temperature": 22.0, "recorded_at": 3000000},
                {"address": "", "temperature": 23.0, "recorded_at": 3000001},
                {"temperature": 24.0, "recorded_at": 3000002},
                {"address": "S-VALID2", "recorded_at": 3000003},
            ],
        }
        resp = client.post("/api/sensor/data", json=payload)
        assert resp.status_code == 201
        assert resp.get_json()["inserted"] == 1

    def test_pruning_old_readings(self, client, db):
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [
                {"address": "S-PRUNE", "temperature": float(i), "recorded_at": 4000000 + i}
                for i in range(5)
            ],
            "keep_count": 3,
        }
        resp = client.post("/api/sensor/data", json=payload)
        assert resp.status_code == 201
        assert resp.get_json()["inserted"] == 5

        count = db.execute(
            "SELECT COUNT(*) FROM readings r JOIN sensors s ON r.sensor_id = s.id WHERE s.sensor_address = ?",
            ("S-PRUNE",),
        ).fetchone()[0]
        assert count == 3


class TestGetSensorData:
    def test_get_sensor_data_returns_temperatures(self, client, sample_data):
        resp = client.get("/api/sensor/data?sensor_id=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert data["address"] == "SENSOR-001"
        assert data["data"] == [22.5, 23.0]

    def test_get_sensor_data_missing_sensor_id(self, client):
        resp = client.get("/api/sensor/data")
        assert resp.status_code == 400

    def test_get_sensor_data_access_denied(self, client):
        resp = client.get("/api/sensor/data?sensor_id=999")
        assert resp.status_code == 403


class TestRenameSensor:
    def test_rename_sensor_success(self, client, sample_data):
        resp = client.put(
            "/api/sensor/rename",
            json={"sensor_id": 1, "location": "New Room"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_rename_sensor_updates_db(self, client, db, sample_data):
        client.put(
            "/api/sensor/rename",
            json={"sensor_id": 1, "location": "Updated Room"},
        )
        row = db.execute("SELECT location FROM sensors WHERE id = 1").fetchone()
        assert row["location"] == "Updated Room"

    def test_rename_sensor_missing_fields(self, client):
        resp = client.put("/api/sensor/rename", json={"sensor_id": 1})
        assert resp.status_code == 400

    def test_rename_sensor_no_access(self, client):
        resp = client.put(
            "/api/sensor/rename",
            json={"sensor_id": 999, "location": "Anywhere"},
        )
        assert resp.status_code == 403


class TestDeviceInfo:
    def test_device_info_returns_sensors(self, client, sample_data):
        resp = client.get("/api/device/info")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2
        assert len(data["sensors"]) == 2

    def test_device_info_contains_expected_fields(self, client, sample_data):
        resp = client.get("/api/device/info")
        sensor = resp.get_json()["sensors"][0]
        assert "sensor_id" in sensor
        assert "address" in sensor
        assert "location" in sensor
        assert "online" in sensor
        assert "controller_mac" in sensor

    def test_device_info_empty_for_no_controllers(self, client):
        import endpoint
        endpoint._blacklist.clear()
        resp = client.get("/api/device/info")
        data = resp.get_json()
        assert data["count"] == 0
        assert data["sensors"] == []
