import sqlite3
import time
import pytest
from app.db import seed_admin

TEST_PASSWORD = "Admin123456!"
TEST_DEVICE_KEY = "test-device-key-for-testing"

APP_MACS = [
    "00:01:02:03:04:05", "00:11:22:33:44:55", "00:AA:BB:CC:DD:EE",
    "00:DD:EE:FF:00:11", "00:22:33:44:55:66", "AA:BB:CC:DD:EE:FF",
    "11:22:33:44:55:66", "66:77:88:99:AA:BB",
]


@pytest.fixture
def app(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("app.config.Config.DB_PATH", db_path)
    monkeypatch.setattr("app.config.Config.SECRET_KEY", "test-secret-key-not-for-production")
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    seed_admin("admin", TEST_PASSWORD, db_path)
    from app.device_auth import hash_api_key
    key_hash = hash_api_key(TEST_DEVICE_KEY)
    ts = int(time.time())
    with sqlite3.connect(db_path) as conn:
        for mac in APP_MACS:
            conn.execute(
                "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
                (mac, ts, ts, 0),
            )
            conn.execute(
                "INSERT OR IGNORE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, 0)",
                (mac, key_hash),
            )
    return application


@pytest.fixture(autouse=True)
def _app_context(app):
    with app.app_context():
        yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200, "auth_headers: login failed"
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db(app):
    from app.db import get_db
    conn = get_db()
    yield conn


@pytest.fixture
def sample_data(db):
    ts = 0
    db.execute(
        "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
        ("AA:BB:CC:DD:EE:FF", ts, ts, 2),
    )
    db.execute(
        "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
        ("11:22:33:44:55:66", ts, ts, 1),
    )
    db.execute(
        "INSERT OR IGNORE INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
        ("SENSOR-001", "AA:BB:CC:DD:EE:FF", "Living Room"),
    )
    db.execute(
        "INSERT OR IGNORE INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
        ("SENSOR-002", "AA:BB:CC:DD:EE:FF", "Bedroom"),
    )
    db.execute(
        "INSERT OR IGNORE INTO sensors (sensor_address, controller_mac, location) VALUES (?, ?, ?)",
        ("SENSOR-003", "11:22:33:44:55:66", "Garage"),
    )
    for sid, temp, rec_ts in [(1, 22.5, ts), (1, 23.0, ts + 1), (2, 19.8, ts + 2)]:
        db.execute(
            "INSERT INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
            (sid, temp, rec_ts),
        )
    db.execute(
        "INSERT OR IGNORE INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
        (1, "AA:BB:CC:DD:EE:FF"),
    )
    from app.device_auth import hash_api_key
    key_hash = hash_api_key(TEST_DEVICE_KEY)
    db.execute(
        "INSERT OR IGNORE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, ?)",
        ("AA:BB:CC:DD:EE:FF", key_hash, ts),
    )
    db.execute(
        "INSERT OR IGNORE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, ?)",
        ("11:22:33:44:55:66", key_hash, ts),
    )
    db.commit()
    return {
        "sensor_1_id": 1,
        "sensor_2_id": 2,
        "sensor_3_id": 3,
        "controller_1": "AA:BB:CC:DD:EE:FF",
        "controller_2": "11:22:33:44:55:66",
        "user_admin_id": 1,
        "temps_sensor_1": [22.5, 23.0],
        "temps_sensor_2": [19.8],
    }


MAC_A1 = "00:AA:00:00:00:01"
MAC_A2 = "00:AA:00:00:00:02"
MAC_B1 = "00:BB:00:00:00:01"
MAC_B2 = "00:BB:00:00:00:02"
MAC_C1 = "00:CC:00:00:00:01"
MAC_C2 = "00:CC:00:00:00:02"
ALL_MULTI_MACS = [MAC_A1, MAC_A2, MAC_B1, MAC_B2, MAC_C1, MAC_C2]


@pytest.fixture
def multi_user_data(client, auth_headers, db):
    from app.device_auth import hash_api_key
    key_hash = hash_api_key(TEST_DEVICE_KEY)

    for mac in ALL_MULTI_MACS:
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
            (mac, 0, 0, 1),
        )
        db.execute(
            "INSERT OR IGNORE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, ?)",
            (mac, key_hash, 0),
        )
    db.commit()

    users = {}
    for name in ["alice", "bob", "charlie"]:
        resp = client.post(
            "/api/admin/users",
            json={"username": name, "password": "pass12345678!"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        users[name] = resp.get_json()["id"]

    return {
        "users": users,
        "macs": {
            "alice": [MAC_A1, MAC_A2],
            "bob": [MAC_B1, MAC_B2],
            "charlie": [MAC_C1, MAC_C2],
        },
    }
