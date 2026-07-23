import json
import time
from flask import Blueprint, request, g
from werkzeug.security import generate_password_hash
from ..auth import require_auth, require_admin, revoke_all_sessions
from ..audit import log_action
from ..responses import ok, error
from ..schemas import (
    use_schema,
    CreateUserRequest,
    ResetPasswordRequest,
    AssignControllersRequest,
)
from ..db import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def parse_pagination_args():
    limit = request.args.get("limit", DEFAULT_PAGE_SIZE, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)
    return limit, offset


def _get_username(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT username FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return row[0] if row else "unknown"


@admin_bp.route("/users")
@require_auth
@require_admin
def admin_list_users():
    limit, offset = parse_pagination_args()
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    rows = conn.execute("""
        SELECT
            u.id,
            u.username,
            u.role,
            u.created_at,
            GROUP_CONCAT(uc.controller_mac) AS macs
        FROM users u
        LEFT JOIN user_controllers uc ON uc.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()
    users = []
    for uid, username, role, created_at, macs in rows:
        controllers = macs.split(",") if macs else []
        users.append(
            {
                "id": uid,
                "username": username,
                "role": role,
                "created_at": created_at,
                "controllers": controllers,
            }
        )
    return ok({
        "users": users,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_next": offset + limit < total,
    })


@admin_bp.route("/users", methods=["POST"])
@require_auth
@require_admin
@use_schema(CreateUserRequest)
def admin_create_user(data):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (data.username,)
    ).fetchone()
    if existing:
        return error("Username already exists", 400)
    h = generate_password_hash(data.password)
    now = int(time.time() * 1000)
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
        (data.username, h, now),
    )
    new_id = conn.execute(
        "SELECT id FROM users WHERE username = ?", (data.username,)
    ).fetchone()[0]
    username = _get_username(g.user_id)
    log_action(
        g.user_id,
        username,
        "user_created",
        "user",
        str(new_id),
        {"username": data.username},
    )
    return ok({"id": new_id, "username": data.username, "role": "user"}, 201)


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_auth
@require_admin
def admin_delete_user(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        return error("User not found", 404)
    admin_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin'"
    ).fetchone()[0]
    if row[1] == "admin" and admin_count <= 1:
        return error("Cannot delete the last admin", 400)
    revoke_all_sessions(user_id)
    conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    username = _get_username(g.user_id)
    log_action(g.user_id, username, "user_deleted", "user", str(user_id))
    return ok()


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["PUT"])
@require_auth
@require_admin
@use_schema(ResetPasswordRequest)
def admin_reset_password(data, user_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return error("User not found", 404)
    h = generate_password_hash(data.new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (h, user_id))
    revoke_all_sessions(user_id)
    username = _get_username(g.user_id)
    log_action(g.user_id, username, "password_reset", "user", str(user_id))
    return ok()


@admin_bp.route("/users/<int:user_id>/controllers", methods=["PUT"])
@require_auth
@require_admin
@use_schema(AssignControllersRequest)
def admin_assign_controllers(data, user_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return error("User not found", 404)
    conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
    for mac in data.controllers:
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
        {"controllers": data.controllers},
    )
    return ok()


@admin_bp.route("/controllers")
@require_auth
@require_admin
def admin_list_controllers():
    limit, offset = parse_pagination_args()
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM controllers").fetchone()[0]
    rows = conn.execute("""
        SELECT c.mac, c.first_seen, c.last_seen, c.sensor_count,
               uc.user_id as owner_id, u.username as owner_username
        FROM controllers c
        LEFT JOIN user_controllers uc ON uc.controller_mac = c.mac
        LEFT JOIN users u ON u.id = uc.user_id
        ORDER BY c.last_seen DESC, c.mac ASC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()
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
    return ok({
        "controllers": controllers,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_next": offset + limit < total,
    })


@admin_bp.route("/audit")
@require_auth
@require_admin
def admin_audit():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
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
        try:
            parsed_details = json.loads(details) if details else None
        except (json.JSONDecodeError, TypeError):
            parsed_details = {"_raw": details, "_error": "corrupt_json"}
        logs.append(
            {
                "id": log_id,
                "user_id": user_id,
                "username": username,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "details": parsed_details,
                "created_at": created_at,
            }
        )
    return ok({"logs": logs, "total": total, "limit": limit, "offset": offset})
