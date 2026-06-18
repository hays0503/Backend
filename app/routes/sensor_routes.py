import sqlite3
import time
from flask import Blueprint, request, jsonify, g
from ..auth import require_auth
from ..config import Config
from ..sensors import check_sensor_access, get_user_controller_macs
from ..audit import log_action

sensor_bp = Blueprint("sensor", __name__, url_prefix="/api/sensor")
device_bp = Blueprint("device", __name__, url_prefix="/api/device")


@sensor_bp.route("/data", methods=["POST"])
def post_sensor_data():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("readings"), list):
        return jsonify({"error": "Invalid readings format"}), 400
    controller_mac = data.get("controller_mac", "")
    if not controller_mac:
        return jsonify({"error": "controller_mac is required"}), 400
    keep_count = data.get("keep_count", Config.KEEP_COUNT_DEFAULT)
    now = int(time.time() * 1000)
    readings = data["readings"]
    inserted = 0
    duplicates = 0
    with sqlite3.connect(Config.DB_PATH) as conn:
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
            address = r.get("address", "")
            temperature = r.get("temperature")
            recorded_at = r.get("recorded_at")
            if not address or temperature is None or not recorded_at:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO sensors (sensor_address, controller_mac) VALUES (?, ?)",
                (address, controller_mac),
            )
            sensor_row = conn.execute(
                "SELECT id FROM sensors WHERE sensor_address = ?", (address,)
            ).fetchone()
            if not sensor_row:
                continue
            sensor_id = sensor_row[0]
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO readings (sensor_id, temperature, recorded_at) VALUES (?, ?, ?)",
                    (sensor_id, temperature, recorded_at),
                )
                if conn.total_changes > 0:
                    inserted += 1
                else:
                    duplicates += 1
            except Exception:
                duplicates += 1
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
    return (
        jsonify(
            {
                "inserted": inserted,
                "duplicates": duplicates,
                "server_time": now,
            }
        ),
        201,
    )


@sensor_bp.route("/data", methods=["GET"])
@require_auth
def get_sensor_data():
    sensor_id = request.args.get("sensor_id", type=int)
    if not sensor_id:
        return jsonify({"error": "sensor_id is required"}), 400
    sensor = check_sensor_access(sensor_id, g.user_id)
    if sensor is None:
        return jsonify({"error": "Access denied"}), 403
    with sqlite3.connect(Config.DB_PATH) as conn:
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
    return jsonify({"data": temps, "address": sensor[1]})


@sensor_bp.route("/rename", methods=["PUT"])
@require_auth
def rename_sensor():
    data = request.get_json(silent=True)
    if not data or not data.get("sensor_id") or not data.get("location"):
        return jsonify({"error": "sensor_id and location are required"}), 400
    sensor_id = data["sensor_id"]
    location = data["location"]
    sensor = check_sensor_access(sensor_id, g.user_id)
    if sensor is None:
        return jsonify({"error": "Access denied"}), 403
    with sqlite3.connect(Config.DB_PATH) as conn:
        conn.execute(
            "UPDATE sensors SET location = ? WHERE id = ?", (location, sensor_id)
        )
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE id = ?", (g.user_id,)
        ).fetchone()
    username = row[0] if row else "unknown"
    log_action(
        g.user_id,
        username,
        "sensor_renamed",
        "sensor",
        str(sensor_id),
        {"location": location},
    )
    return jsonify({"success": True})


@device_bp.route("/info")
@require_auth
def device_info():
    macs = get_user_controller_macs(g.user_id)
    if not macs:
        return jsonify({"count": 0, "sensors": []})
    placeholders = ",".join("?" for _ in macs)
    now_ms = int(time.time() * 1000)
    with sqlite3.connect(Config.DB_PATH) as conn:
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
    return jsonify({"count": len(sensors), "sensors": sensors})
