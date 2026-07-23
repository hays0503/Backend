import time
import pytest

TEST_DEVICE_KEY = "test-device-key-for-testing"

TEST_MAC_POST = "00:01:02:03:04:05"
TEST_MAC_MULTI = "00:11:22:33:44:55"
TEST_MAC_DUP = "00:AA:BB:CC:DD:EE"
TEST_MAC_UPSERT = "00:DD:EE:FF:00:11"
TEST_MAC_VALID = "00:22:33:44:55:66"


def _post_reading(client, mac, address, temp=25.0, ts=None):
    ts = ts or int(time.time() * 1000)
    return client.post(
        "/api/sensor/data",
        json={
            "controller_mac": mac,
            "readings": [{"address": address, "temperature": temp, "recorded_at": ts}],
        },
        headers={"X-Device-Key": TEST_DEVICE_KEY},
    )


class TestPostSensorDataBlackBox:
    def test_post_single_reading_returns_201_and_counts(self, client):
        """POST sensor data -> 201 with inserted count."""
        resp = _post_reading(client, TEST_MAC_POST, "ADDR-POST-1", 22.0)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.get_json()}"
        assert resp.get_json()["inserted"] == 1
        assert resp.get_json()["duplicates"] == 0

    def test_post_multiple_readings(self, client):
        """3 readings -> inserted=3."""
        now = int(time.time() * 1000)
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": TEST_MAC_MULTI,
                "readings": [
                    {"address": "A-MULTI-1", "temperature": 20.0, "recorded_at": now},
                    {"address": "A-MULTI-2", "temperature": 21.0, "recorded_at": now + 1},
                    {"address": "A-MULTI-3", "temperature": 22.0, "recorded_at": now + 2},
                ],
            },
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 201
        assert resp.get_json()["inserted"] == 3

    def test_duplicate_reading_not_counted_twice(self, client):
        """Same data posted twice -> only 1 reading stored."""
        mac = TEST_MAC_DUP
        addr = "ADDR-DUP-1"
        r1 = _post_reading(client, mac, addr, 22.0)
        assert r1.status_code == 201

        r2 = _post_reading(client, mac, addr, 22.0)
        assert r2.status_code == 201

    def test_missing_controller_mac_returns_400(self, client):
        resp = client.post(
            "/api/sensor/data",
            json={"readings": [{"address": "X", "temperature": 1.0, "recorded_at": 1}]},
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 400

    def test_invalid_readings_format_returns_400(self, client):
        resp = client.post(
            "/api/sensor/data",
            json={"controller_mac": "00:00:00:00:00:00"},
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 400

    def test_non_json_body_returns_400(self, client):
        resp = client.post(
            "/api/sensor/data",
            data="not json",
            content_type="text/plain",
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 400

    def test_controller_upserted_with_sensor_count(self, client, auth_headers):
        """New controller auto-created on POST with correct sensor_count."""
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": TEST_MAC_UPSERT,
                "readings": [{"address": "ADDR-UPS-1", "temperature": 22.0, "recorded_at": int(time.time() * 1000)}],
            },
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 201

        ctrls = client.get("/api/admin/controllers", headers=auth_headers).get_json()["controllers"]
        match = [c for c in ctrls if c["mac"] == TEST_MAC_UPSERT]
        assert len(match) == 1
        assert match[0]["sensor_count"] >= 1

    def test_reading_with_empty_address_returns_400(self, client):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": TEST_MAC_VALID,
                "readings": [
                    {"address": "", "temperature": 23.0, "recorded_at": 3000000},
                ],
            },
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 400

    def test_reading_missing_temperature_returns_400(self, client):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": TEST_MAC_VALID,
                "readings": [
                    {"address": "S-NO-TEMP", "recorded_at": 3000000},
                ],
            },
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 400

    def test_pruning_old_readings_keeps_only_keep_count(self, client, sample_data, auth_headers):
        """POST with keep_count prunes oldest readings beyond that count."""
        addr = "ADDR-PRUNE-1"
        mac = sample_data["controller_1"]
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": mac,
                "readings": [
                    {"address": addr, "temperature": float(i), "recorded_at": int(time.time() * 1000) + i}
                    for i in range(5)
                ],
                "keep_count": 3,
            },
            headers={"X-Device-Key": TEST_DEVICE_KEY},
        )
        assert resp.status_code == 201
        assert resp.get_json()["inserted"] == 5

        info = client.get("/api/device/info", headers=auth_headers).get_json()
        sensor = next(s for s in info["sensors"] if s["address"] == addr)
        data_resp = client.get(f"/api/sensor/data?sensor_id={sensor['sensor_id']}", headers=auth_headers)
        assert data_resp.status_code == 200
        assert len(data_resp.get_json()["data"]) == 3


class TestGetSensorDataBlackBox:
    def test_get_returns_temperatures_in_asc_order(self, client, sample_data, auth_headers):
        resp = client.get(f"/api/sensor/data?sensor_id={sample_data['sensor_1_id']}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"] == [22.5, 23.0], "must be sorted ASC"
        assert body["address"] == "SENSOR-001"

    def test_get_without_sensor_id_returns_400(self, client, auth_headers):
        resp = client.get("/api/sensor/data", headers=auth_headers)
        assert resp.status_code == 400

    def test_get_nonexistent_sensor_returns_403(self, client, auth_headers):
        resp = client.get("/api/sensor/data?sensor_id=99999", headers=auth_headers)
        assert resp.status_code == 403

    def test_get_sensor_without_access_returns_403(self, client, sample_data, auth_headers):
        resp = client.get(f"/api/sensor/data?sensor_id={sample_data['sensor_3_id']}", headers=auth_headers)
        assert resp.status_code == 403


class TestRenameSensorBlackBox:
    def test_rename_sensor_returns_200(self, client, sample_data, auth_headers):
        resp = client.put(
            "/api/sensor/rename",
            json={"sensor_id": sample_data["sensor_1_id"], "location": "Kitchen"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_rename_persists_in_device_info(self, client, sample_data, auth_headers):
        client.put(
            "/api/sensor/rename",
            json={"sensor_id": sample_data["sensor_1_id"], "location": "Kitchen"},
            headers=auth_headers,
        )
        resp = client.get("/api/device/info", headers=auth_headers)
        sensors = resp.get_json()["sensors"]
        kitchen = [s for s in sensors if s["sensor_id"] == sample_data["sensor_1_id"]]
        assert len(kitchen) == 1
        assert kitchen[0]["location"] == "Kitchen"

    def test_rename_missing_fields_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/sensor/rename",
            json={"sensor_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_rename_without_access_returns_403(self, client, sample_data, auth_headers):
        resp = client.put(
            "/api/sensor/rename",
            json={"sensor_id": sample_data["sensor_3_id"], "location": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestDeviceInfoBlackBox:
    def test_device_info_returns_accessible_sensors(self, client, sample_data, auth_headers):
        resp = client.get("/api/device/info", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 2
        assert len(body["sensors"]) == 2

    def test_device_info_contains_expected_fields(self, client, sample_data, auth_headers):
        resp = client.get("/api/device/info", headers=auth_headers)
        sensor = resp.get_json()["sensors"][0]
        assert set(sensor.keys()) == {"sensor_id", "address", "location", "online", "controller_mac"}
        assert isinstance(sensor["online"], bool)

    def test_sensors_with_old_readings_are_offline(self, client, sample_data, auth_headers):
        resp = client.get("/api/device/info", headers=auth_headers)
        for s in resp.get_json()["sensors"]:
            assert s["online"] is False

    def test_freshly_posted_sensor_is_online(self, client, sample_data, auth_headers):
        addr = "ADDR-ONLINE-1"
        _post_reading(client, sample_data["controller_1"], addr, 22.0)
        resp = client.get("/api/device/info", headers=auth_headers)
        online_sensors = [s for s in resp.get_json()["sensors"] if s["online"]]
        assert any(s["address"] == addr for s in online_sensors)
