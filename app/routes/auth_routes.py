import sqlite3
from flask import Blueprint, g
from werkzeug.security import check_password_hash, generate_password_hash
from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_refresh_token,
    require_auth,
)
from ..audit import log_action
from ..config import Config
from ..sensors import get_user_controller_macs
from ..responses import ok, error
from ..schemas import use_schema, LoginRequest, RefreshRequest, ProfileUpdate

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
@use_schema(LoginRequest)
def login(data):
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (data.username,),
        ).fetchone()
    if not row or not check_password_hash(row[2], data.password):
        return error("Invalid credentials", 401)
    user_id, username, _, role = row
    access_token = create_access_token(user_id, role)
    refresh_token, _ = create_refresh_token(user_id)
    log_action(user_id, username, "login")
    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {"id": user_id, "username": username, "role": role},
        }
    )


@auth_bp.route("/refresh", methods=["POST"])
@use_schema(RefreshRequest)
def refresh(data):
    payload = decode_token(data.refresh_token, "refresh")
    if not payload:
        return error("Invalid refresh token", 401)
    old_jti = payload["jti"]
    revoke_refresh_token(old_jti)
    user_id = payload["user_id"]
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row:
        return error("User not found", 401)
    access_token = create_access_token(row[0], row[2])
    refresh_token, _ = create_refresh_token(row[0])
    return ok({"access_token": access_token, "refresh_token": refresh_token})


@auth_bp.route("/me")
@require_auth
def auth_me():
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (g.user_id,)
        ).fetchone()
    if not row:
        return error("User not found", 404)
    controllers = get_user_controller_macs(g.user_id)
    return ok(
        {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "controllers": controllers,
        }
    )


@auth_bp.route("/profile", methods=["PUT"])
@require_auth
@use_schema(ProfileUpdate)
def auth_profile(data):
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
    if not row or not check_password_hash(row[2], data.current_password):
        return error("Current password is incorrect", 400)
    user_id, username, _, role = row
    update_fields = []
    update_values = []
    if data.username:
        with sqlite3.connect(Config.DB_PATH) as conn2:
            existing = conn2.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (data.username, user_id),
            ).fetchone()
        if existing:
            return error("Username already exists", 400)
        update_fields.append("username = ?")
        update_values.append(data.username)
        username = data.username
    if data.password:
        update_fields.append("password_hash = ?")
        update_values.append(generate_password_hash(data.password))
    if update_fields:
        with sqlite3.connect(Config.DB_PATH) as conn2:
            conn2.execute(
                f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
                (*update_values, user_id),
            )
    log_action(user_id, username, "profile_updated")
    return ok({"id": user_id, "username": username, "role": role})
