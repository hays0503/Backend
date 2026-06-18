import sqlite3
import time
import pytest


@pytest.fixture
def app(monkeypatch, tmp_path):
    import endpoint
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("endpoint.DB_PATH", db_path)
    endpoint.init_db()
    endpoint._blacklist.clear()
    endpoint.app.config["TESTING"] = True
    return endpoint.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    import endpoint
    conn = sqlite3.connect(endpoint.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def sample_data(db):
    now = int(time.time() * 1000)
    db.execute(
        "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
        ("AA:BB:CC:DD:EE:FF", now, now, 2),
    )
    db.execute(
        "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, ?)",
        ("11:22:33:44:55:66", now, now, 1),
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
    db.execute(
        "INSERT INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
        (1, 22.5, now - 10000),
    )
    db.execute(
        "INSERT INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
        (1, 23.0, now),
    )
    db.execute(
        "INSERT INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
        (2, 19.8, now),
    )
    db.execute(
        "INSERT OR IGNORE INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
        (1, "AA:BB:CC:DD:EE:FF"),
    )
    db.commit()
    return db
