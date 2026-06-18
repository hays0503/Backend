import sqlite3
import time
import os
import json
import uuid
from functools import wraps

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

app = Flask(__name__)

CORS(app, origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensors.db")
SECRET_KEY = "change-me-in-production-yescada-2026"
ACCESS_TOKEN_EXPIRES_SEC = 3600
REFRESH_TOKEN_EXPIRES_SEC = 604800
KEEP_COUNT_DEFAULT = 1000
_blacklist = set()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS controllers (
                mac TEXT PRIMARY KEY,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                sensor_count INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_address TEXT NOT NULL UNIQUE,
                controller_mac TEXT NOT NULL REFERENCES controllers(mac),
                location TEXT DEFAULT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id INTEGER NOT NULL REFERENCES sensors(id),
                temperature REAL NOT NULL,
                recorded_at INTEGER NOT NULL,
                UNIQUE(sensor_id, recorded_at)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_sensor_time
            ON readings(sensor_id, recorded_at DESC)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_controllers (
                user_id INTEGER NOT NULL REFERENCES users(id),
                controller_mac TEXT NOT NULL REFERENCES controllers(mac),
                PRIMARY KEY (user_id, controller_mac)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                details TEXT,
                created_at INTEGER NOT NULL
            )
        """)

        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] == 0:
            h = generate_password_hash("admin")
            now = int(time.time() * 1000)
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                ("admin", h, now),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE username = ?", ("admin",)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, 'system', 'admin_seeded', 'user', 'admin', ?, ?)",
                (user_id, json.dumps({"username": "admin"}), now),
            )
            print("WARNING: Default admin created: admin / admin")


init_db()


def create_access_token(user_id, role):
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "exp": int(time.time()) + ACCESS_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id, jti=None):
    jti = jti or str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": int(time.time()) + REFRESH_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256"), jti


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            return None
        if expected_type == "refresh" and payload.get("jti") in _blacklist:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing token"}), 401
        token = auth[7:]
        payload = decode_token(token, "access")
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.user_id = payload["user_id"]
        g.user_role = payload["role"]
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if getattr(g, "user_role", None) != "admin":
            return jsonify({"error": "Admin only"}), 403
        return f(*args, **kwargs)
    return wrapper


def log_action(user_id, username, action, target_type=None, target_id=None, details=None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, action, target_type, target_id,
             json.dumps(details) if details else None,
             int(time.time() * 1000)),
        )


def get_user_controller_macs(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT controller_mac FROM user_controllers WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [r[0] for r in rows]


def check_sensor_access(sensor_id, user_id):
    macs = get_user_controller_macs(user_id)
    if not macs:
        return None
    placeholders = ",".join("?" for _ in macs)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            f"SELECT id, sensor_address, location, controller_mac FROM sensors WHERE id = ? AND controller_mac IN ({placeholders})",
            (sensor_id, *macs),
        ).fetchone()
    return row


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Missing credentials"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (data["username"],),
        ).fetchone()
    if not row or not check_password_hash(row[2], data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401
    user_id, username, _, role = row
    access_token = create_access_token(user_id, role)
    refresh_token, _ = create_refresh_token(user_id)
    log_action(user_id, username, "login")
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user_id, "username": username, "role": role},
    })


@app.route("/api/auth/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True)
    if not data or not data.get("refresh_token"):
        return jsonify({"error": "Missing refresh token"}), 400
    payload = decode_token(data["refresh_token"], "refresh")
    if not payload:
        return jsonify({"error": "Invalid refresh token"}), 401
    old_jti = payload["jti"]
    _blacklist.add(old_jti)
    user_id = payload["user_id"]
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "User not found"}), 401
    access_token = create_access_token(row[0], row[2])
    refresh_token, _ = create_refresh_token(row[0])
    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@app.route("/api/auth/me")
@require_auth
def auth_me():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (g.user_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "User not found"}), 404
    controllers = get_user_controller_macs(g.user_id)
    return jsonify({
        "id": row[0],
        "username": row[1],
        "role": row[2],
        "controllers": controllers,
    })


@app.route("/api/auth/profile", methods=["PUT"])
@require_auth
def auth_profile():
    data = request.get_json(silent=True)
    if not data or not data.get("current_password"):
        return jsonify({"error": "Current password is required"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
    if not row or not check_password_hash(row[2], data["current_password"]):
        return jsonify({"error": "Current password is incorrect"}), 400
    user_id, username, _, role = row
    update_fields = []
    update_values = []
    if data.get("username"):
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (data["username"], user_id),
        ).fetchone()
        if existing:
            return jsonify({"error": "Username already exists"}), 400
        update_fields.append("username = ?")
        update_values.append(data["username"])
        username = data["username"]
    if data.get("password"):
        update_fields.append("password_hash = ?")
        update_values.append(generate_password_hash(data["password"]))
    if update_fields:
        conn.execute(
            f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
            (*update_values, user_id),
        )
    log_action(user_id, username, "profile_updated")
    return jsonify({"id": user_id, "username": username, "role": role})


@app.route("/api/sensor/data", methods=["POST"])
def post_sensor_data():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("readings"), list):
        return jsonify({"error": "Invalid readings format"}), 400
    controller_mac = data.get("controller_mac", "")
    if not controller_mac:
        return jsonify({"error": "controller_mac is required"}), 400
    keep_count = data.get("keep_count", KEEP_COUNT_DEFAULT)
    now = int(time.time() * 1000)
    readings = data["readings"]
    inserted = 0
    duplicates = 0
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO controllers (mac, first_seen, last_seen, sensor_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET
                last_seen = excluded.last_seen,
                sensor_count = excluded.sensor_count
        """, (controller_mac, now, now, len(readings)))
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
            conn.execute("""
                DELETE FROM readings WHERE sensor_id = ? AND id NOT IN (
                    SELECT id FROM readings WHERE sensor_id = ? ORDER BY recorded_at DESC LIMIT ?
                )
            """, (sid, sid, keep_count))
    return jsonify({
        "inserted": inserted,
        "duplicates": duplicates,
        "server_time": now,
    }), 201


@app.route("/api/sensor/data", methods=["GET"])
@require_auth
def get_sensor_data():
    sensor_id = request.args.get("sensor_id", type=int)
    if not sensor_id:
        return jsonify({"error": "sensor_id is required"}), 400
    sensor = check_sensor_access(sensor_id, g.user_id)
    if sensor is None:
        return jsonify({"error": "Access denied"}), 403
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT temperature FROM readings WHERE sensor_id = ? ORDER BY recorded_at ASC LIMIT 100",
            (sensor_id,),
        ).fetchall()
    temps = [r[0] for r in rows]
    return jsonify({"data": temps, "address": sensor[1]})


@app.route("/api/sensor/rename", methods=["PUT"])
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE sensors SET location = ? WHERE id = ?", (location, sensor_id))
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
    username = row[0] if row else "unknown"
    log_action(g.user_id, username, "sensor_renamed", "sensor", str(sensor_id), {"location": location})
    return jsonify({"success": True})


@app.route("/api/device/info")
@require_auth
def device_info():
    macs = get_user_controller_macs(g.user_id)
    if not macs:
        return jsonify({"count": 0, "sensors": []})
    placeholders = ",".join("?" for _ in macs)
    now_ms = int(time.time() * 1000)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"""
            SELECT s.id, s.sensor_address, s.location, s.controller_mac, MAX(r.recorded_at) as last_reading
            FROM sensors s
            LEFT JOIN readings r ON r.sensor_id = s.id
            WHERE s.controller_mac IN ({placeholders})
            GROUP BY s.id
        """, macs).fetchall()
    sensors = []
    for sid, address, location, controller_mac, last_reading in rows:
        online = last_reading is not None and (now_ms - last_reading) < 30000
        sensors.append({
            "sensor_id": sid,
            "address": address,
            "location": location if location else address,
            "online": online,
            "controller_mac": controller_mac,
        })
    return jsonify({"count": len(sensors), "sensors": sensors})


@app.route("/api/admin/users")
@require_auth
@require_admin
def admin_list_users():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    users = []
    for uid, username, role, created_at in rows:
        controllers = get_user_controller_macs(uid)
        users.append({
            "id": uid,
            "username": username,
            "role": role,
            "created_at": created_at,
            "controllers": controllers,
        })
    return jsonify({"users": users})


@app.route("/api/admin/users", methods=["POST"])
@require_auth
@require_admin
def admin_create_user():
    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password are required"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (data["username"],)
        ).fetchone()
        if existing:
            return jsonify({"error": "Username already exists"}), 400
        h = generate_password_hash(data["password"])
        now = int(time.time() * 1000)
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
            (data["username"], h, now),
        )
        new_id = conn.execute(
            "SELECT id FROM users WHERE username = ?", (data["username"],)
        ).fetchone()[0]
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
    username = row[0] if row else "unknown"
    log_action(g.user_id, username, "user_created", "user", str(new_id), {"username": data["username"]})
    return jsonify({"id": new_id, "username": data["username"], "role": "user"}), 201


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_auth
@require_admin
def admin_delete_user(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        admin_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
        if row[1] == "admin" and admin_count <= 1:
            return jsonify({"error": "Cannot delete the last admin"}), 400
        conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
    username = row[0] if row else "unknown"
    log_action(g.user_id, username, "user_deleted", "user", str(user_id))
    return jsonify({"success": True})


@app.route("/api/admin/users/<int:user_id>/reset-password", methods=["PUT"])
@require_auth
@require_admin
def admin_reset_password(user_id):
    data = request.get_json(silent=True)
    if not data or not data.get("new_password"):
        return jsonify({"error": "new_password is required"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        h = generate_password_hash(data["new_password"])
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (h, user_id))
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
    username = row[0] if row else "unknown"
    log_action(g.user_id, username, "password_reset", "user", str(user_id))
    return jsonify({"success": True})


@app.route("/api/admin/users/<int:user_id>/controllers", methods=["PUT"])
@require_auth
@require_admin
def admin_assign_controllers(user_id):
    data = request.get_json(silent=True)
    if not data or "controllers" not in data:
        return jsonify({"error": "controllers list is required"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
        for mac in data["controllers"]:
            conn.execute(
                "INSERT INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
                (user_id, mac),
            )
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
    username = row[0] if row else "unknown"
    log_action(g.user_id, username, "controllers_assigned", "user", str(user_id),
               {"controllers": data["controllers"]})
    return jsonify({"success": True})


@app.route("/api/admin/controllers")
@require_auth
@require_admin
def admin_list_controllers():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT c.mac, c.first_seen, c.last_seen, c.sensor_count,
                   uc.user_id as owner_id, u.username as owner_username
            FROM controllers c
            LEFT JOIN user_controllers uc ON uc.controller_mac = c.mac
            LEFT JOIN users u ON u.id = uc.user_id
            ORDER BY c.last_seen DESC
        """).fetchall()
    controllers = []
    for mac, first_seen, last_seen, sensor_count, owner_id, owner_username in rows:
        ctrl = {
            "mac": mac,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "sensor_count": sensor_count,
            "owner_id": owner_id,
            "owner_username": owner_username,
        }
        controllers.append(ctrl)
    return jsonify({"controllers": controllers})


@app.route("/api/admin/audit")
@require_auth
@require_admin
def admin_audit():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, user_id, username, action, target_type, target_id, details, created_at FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    logs = []
    for log_id, user_id, username, action, target_type, target_id, details, created_at in rows:
        logs.append({
            "id": log_id,
            "user_id": user_id,
            "username": username,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": json.loads(details) if details else None,
            "created_at": created_at,
        })
    return jsonify({"logs": logs})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
