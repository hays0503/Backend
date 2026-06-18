import time
import uuid
from functools import wraps
from flask import request, jsonify, g
import jwt
from .config import Config


_blacklist = set()


def create_access_token(user_id, role):
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "exp": int(time.time()) + Config.ACCESS_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id, jti=None):
    jti = jti or str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": int(time.time()) + Config.REFRESH_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256"), jti


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            return None
        if expected_type == "refresh" and payload.get("jti") in _blacklist:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def revoke_refresh_token(jti):
    _blacklist.add(jti)


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
