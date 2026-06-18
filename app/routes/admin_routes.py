import sqlite3
import json
import time
from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash
from ..auth import require_auth, require_admin
from ..config import Config
from ..sensors import get_user_controller_macs
from ..audit import log_action

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _get_username(user_id):
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else "unknown"


@admin_bp.route("/users")
@require_auth
@require_admin
def admin_list_users():
    with sqlite3.connect(Config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
    users = []
    for uid, username, role, created_at in rows:
        controllers = get_user_controller_macs(uid)
        users.append(
            {
                "id": uid,
                "username": username,
                "role": role,
                "created_at": created_at,
                "controllers": controllers,
            }
        )
    return jsonify({"users": users})


@admin_bp.route("/users", methods=["POST"])
@require_auth
@require_admin
def admin_create_user():
    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password are required"}), 400
    with sqlite3.connect(Config.DB_PATH) as conn:
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
    username = _get_username(g.user_id)
    log_action(
        g.user_id,
        username,
        "user_created",
        "user",
        str(new_id),
        {"username": data["username"]},
    )
    return jsonify({"id": new_id, "username": data["username"], "role": "user"}), 201


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_auth
@require_admin
def admin_delete_user(user_id):
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        admin_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
        if row[1] == "admin" and admin_count <= 1:
            return jsonify({"error": "Cannot delete the last admin"}), 400
        conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    username = _get_username(g.user_id)
    log_action(g.user_id, username, "user_deleted", "user", str(user_id))
    return jsonify({"success": True})


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["PUT"])
@require_auth
@require_admin
def admin_reset_password(user_id):
    data = request.get_json(silent=True)
    if not data or not data.get("new_password"):
        return jsonify({"error": "new_password is required"}), 400
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        h = generate_password_hash(data["new_password"])
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (h, user_id))
    username = _get_username(g.user_id)
    log_action(g.user_id, username, "password_reset", "user", str(user_id))
    return jsonify({"success": True})


@admin_bp.route("/users/<int:user_id>/controllers", methods=["PUT"])
@require_auth
@require_admin
def admin_assign_controllers(user_id):
    data = request.get_json(silent=True)
    if not data or "controllers" not in data:
        return jsonify({"error": "controllers list is required"}), 400
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
        for mac in data["controllers"]:
            conn.execute(
                "INSERT INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
                (user_id, mac),
            )
    username = _get_username(g.user_id)
    log_action(
        g.user_id,
        username,
        "controllers_assigned",
        "user",
        str(user_id),
        {"controllers": data["controllers"]},
    )
    return jsonify({"success": True})


@admin_bp.route("/controllers")
@require_auth
@require_admin
def admin_list_controllers():
    with sqlite3.connect(Config.DB_PATH) as conn:
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


@admin_bp.route("/audit")
@require_auth
@require_admin
def admin_audit():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    with sqlite3.connect(Config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, user_id, username, action, target_type, target_id, details, created_at FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    logs = []
    for (
        log_id,
        user_id,
        username,
        action,
        target_type,
        target_id,
        details,
        created_at,
    ) in rows:
        logs.append(
            {
                "id": log_id,
                "user_id": user_id,
                "username": username,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "details": json.loads(details) if details else None,
                "created_at": created_at,
            }
        )
    return jsonify({"logs": logs})
