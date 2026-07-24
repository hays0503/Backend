import time
from werkzeug.security import check_password_hash, generate_password_hash
from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_session,
    store_session,
    revoke_all_sessions,
)
from ..config import Config
from ..db import get_db
from ..errors import UnauthorizedError, NotFoundError, ValidationError
from .sensor_service import get_user_controller_macs


def login(username, password):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not row or not check_password_hash(row[2], password):
        raise UnauthorizedError("Invalid credentials")
    user_id, username, _, role = row
    access_token = create_access_token(user_id, role)
    refresh_token, jti = create_refresh_token(user_id)
    expires_at = int(time.time()) + Config.REFRESH_TOKEN_EXPIRES_SEC
    store_session(jti, user_id, expires_at)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user_id, "username": username, "role": role},
    }


def refresh(refresh_token):
    payload = decode_token(refresh_token, "refresh")
    if not payload:
        raise UnauthorizedError("Invalid refresh token")
    old_jti = payload["jti"]
    revoke_session(old_jti)
    user_id = payload["user_id"]
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        raise UnauthorizedError("User not found")
    access_token = create_access_token(row[0], row[2])
    refresh_token, new_jti = create_refresh_token(row[0])
    expires_at = int(time.time()) + Config.REFRESH_TOKEN_EXPIRES_SEC
    store_session(new_jti, row[0], expires_at)
    return {"access_token": access_token, "refresh_token": refresh_token}


def get_current_user(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        raise NotFoundError("User not found")
    controllers = get_user_controller_macs(user_id)
    return {
        "id": row[0],
        "username": row[1],
        "role": row[2],
        "controllers": controllers,
    }


def update_profile(user_id, current_password, new_username=None, new_password=None):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or not check_password_hash(row[2], current_password):
        raise ValidationError("Current password is incorrect")
    user_id, username, _, role = row
    update_fields = []
    update_values = []
    if new_username:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (new_username, user_id),
        ).fetchone()
        if existing:
            raise ValidationError("Username already exists")
        update_fields.append("username = ?")
        update_values.append(new_username)
        username = new_username
    if new_password:
        update_fields.append("password_hash = ?")
        update_values.append(generate_password_hash(new_password))
    if update_fields:
        conn.execute(
            f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
            (*update_values, user_id),
        )
    if new_password:
        revoke_all_sessions(user_id)
    return {"id": user_id, "username": username, "role": role}
