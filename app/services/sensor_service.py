import sqlite3
import time
from ..db import get_db
from ..errors import NotFoundError, ForbiddenError


def get_user_controller_macs(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT controller_mac FROM user_controllers WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return [r[0] for r in rows]


def check_sensor_access(sensor_id, user_id):
    macs = get_user_controller_macs(user_id)
    if not macs:
        return None
    placeholders = ",".join("?" for _ in macs)
    conn = get_db()
    row = conn.execute(
        f"SELECT id, sensor_address, location, controller_mac FROM sensors WHERE id = ? AND controller_mac IN ({placeholders})",
        (sensor_id, *macs),
    ).fetchone()
    return row


def ingest_readings(controller_mac, readings, keep_count):
    now = int(time.time() * 1000)
    inserted = 0
    duplicates = 0
    conn = get_db()
    conn.execute(
        """
        INSERT INTO controllers (mac, first_seen, last_seen, sensor_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(mac) DO UPDATE SET
            last_seen = excluded.last_seen,
            sensor_count = excluded.sensor_count
    """,
        (controller_mac, now, now, len(readings)),
    )
    for r in readings:
        conn.execute(
            "INSERT OR IGNORE INTO sensors (sensor_address, controller_mac) VALUES (?, ?)",
            (r.address, controller_mac),
        )
        sensor_row = conn.execute(
            "SELECT id FROM sensors WHERE sensor_address = ? AND controller_mac = ?",
            (r.address, controller_mac),
        ).fetchone()
        if not sensor_row:
            continue
        sensor_id = sensor_row[0]
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
                (sensor_id, r.temperature, r.recorded_at),
            )
            if cur.rowcount > 0:
                inserted += 1
            else:
                duplicates += 1
        except sqlite3.Error:
            conn.rollback()
            raise
    sensor_ids = conn.execute(
        "SELECT id FROM sensors WHERE controller_mac = ?", (controller_mac,)
    ).fetchall()
    for (sid,) in sensor_ids:
        conn.execute(
            """
            DELETE FROM readings WHERE sensor_id = ? AND id NOT IN (
                SELECT id FROM readings WHERE sensor_id = ? ORDER BY recorded_at DESC LIMIT ?
            )
        """,
            (sid, sid, keep_count),
        )
    return {"inserted": inserted, "duplicates": duplicates, "server_time": now}


def get_recent_readings(sensor_id, user_id):
    sensor = check_sensor_access(sensor_id, user_id)
    if sensor is None:
        raise ForbiddenError("Access denied")
    conn = get_db()
    rows = conn.execute(
        """
        SELECT temperature
        FROM (
            SELECT temperature, recorded_at
            FROM readings
            WHERE sensor_id = ?
            ORDER BY recorded_at DESC
            LIMIT 100
        )
        ORDER BY recorded_at ASC
        """,
        (sensor_id,),
    ).fetchall()
    temps = [r[0] for r in rows]
    return {"data": temps, "address": sensor[1]}


def rename_sensor(sensor_id, location, user_id):
    sensor = check_sensor_access(sensor_id, user_id)
    if sensor is None:
        raise ForbiddenError("Access denied")
    conn = get_db()
    conn.execute(
        "UPDATE sensors SET location = ? WHERE id = ?",
        (location, sensor_id),
    )
    return sensor_id


def get_device_info(user_id):
    macs = get_user_controller_macs(user_id)
    if not macs:
        return {"count": 0, "sensors": []}
    placeholders = ",".join("?" for _ in macs)
    now_ms = int(time.time() * 1000)
    conn = get_db()
    rows = conn.execute(
        f"""
        SELECT s.id, s.sensor_address, s.location, s.controller_mac, MAX(r.recorded_at) as last_reading
        FROM sensors s
        LEFT JOIN readings r ON r.sensor_id = s.id
        WHERE s.controller_mac IN ({placeholders})
        GROUP BY s.id
    """,
        macs,
    ).fetchall()
    sensors = []
    for sid, address, location, controller_mac, last_reading in rows:
        online = last_reading is not None and (now_ms - last_reading) < 30000
        sensors.append(
            {
                "sensor_id": sid,
                "address": address,
                "location": location if location else address,
                "online": online,
                "controller_mac": controller_mac,
            }
        )
    return {"count": len(sensors), "sensors": sensors}
