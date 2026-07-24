import time
from werkzeug.security import generate_password_hash
from ..db import get_db
from ..errors import NotFoundError, ValidationError


def _get_username(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT username FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return row[0] if row else "unknown"


def list_users(limit, offset):
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
    return {
        "users": users,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_next": offset + limit < total,
    }


def create_user(username, password):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        raise ValidationError("Username already exists")
    h = generate_password_hash(password)
    now = int(time.time() * 1000)
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
        (username, h, now),
    )
    new_id = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()[0]
    return {"id": new_id, "username": username, "role": "user"}


def delete_user(user_id):
    from ..auth import revoke_all_sessions
    conn = get_db()
    row = conn.execute(
        "SELECT id, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        raise NotFoundError("User not found")
    admin_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin'"
    ).fetchone()[0]
    if row[1] == "admin" and admin_count <= 1:
        raise ValidationError("Cannot delete the last admin")
    revoke_all_sessions(user_id)
    conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def reset_password(user_id, new_password):
    from ..auth import revoke_all_sessions
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise NotFoundError("User not found")
    h = generate_password_hash(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (h, user_id))
    revoke_all_sessions(user_id)


def assign_controllers(user_id, controllers):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise NotFoundError("User not found")
    conn.execute("DELETE FROM user_controllers WHERE user_id = ?", (user_id,))
    for mac in controllers:
        conn.execute(
            "INSERT INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
            (user_id, mac),
        )


def list_controllers(limit, offset):
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
    return {
        "controllers": controllers,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_next": offset + limit < total,
    }


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        raise NotFoundError("User not found")
    return {"id": row[0], "username": row[1], "role": row[2]}
