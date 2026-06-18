import sqlite3
import json
import time
import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("app.config.Config.DB_PATH", db_path)
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    from app.config import Config
    conn = sqlite3.connect(Config.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


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
