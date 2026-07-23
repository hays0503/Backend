import time
import uuid
from functools import wraps
from flask import request, jsonify, g
import jwt
from .config import Config
from .db import get_db


def create_access_token(user_id, role):
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
        "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        "exp": now + Config.ACCESS_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id, jti=None):
    jti = jti or str(uuid.uuid4())
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
        "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        "exp": now + Config.REFRESH_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256"), jti


def store_session(jti, user_id, expires_at, token_version=0):
    conn = get_db()
    now = int(time.time())
    conn.execute(
        "INSERT INTO auth_sessions (jti, user_id, token_version, expires_at, revoked_at, created_at) "
        "VALUES (?, ?, ?, ?, NULL, ?)",
        (jti, user_id, token_version, expires_at, now),
    )


def is_session_revoked(jti):
    conn = get_db()
    row = conn.execute(
        "SELECT revoked_at FROM auth_sessions WHERE jti = ?", (jti,)
    ).fetchone()
    if not row:
        return False
    return row[0] is not None


def revoke_session(jti):
    now = int(time.time())
    conn = get_db()
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE jti = ? AND revoked_at IS NULL",
        (now, jti),
    )


def revoke_all_sessions(user_id):
    now = int(time.time())
    conn = get_db()
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (now, user_id),
    )


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms=["HS256"],
            issuer=getattr(Config, "JWT_ISSUER", "yescada-core"),
            audience=getattr(Config, "JWT_AUDIENCE", "yescada-api"),
            leeway=getattr(Config, "JWT_CLOCK_SKEW_SEC", 30),
        )
        if payload.get("type") != expected_type:
            return None
        if expected_type == "refresh" and is_session_revoked(payload.get("jti")):
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
