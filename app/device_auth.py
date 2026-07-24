import hashlib
from functools import wraps
from flask import request, g
from .db import get_db
from .responses import error


def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def require_device_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        device_key = request.headers.get("X-Device-Key")
        if not device_key:
            return error("Missing X-Device-Key header", 401)
        key_hash = hash_api_key(device_key)
        conn = get_db()
        row = conn.execute(
            "SELECT controller_mac FROM controller_api_keys WHERE key_hash = ?", (key_hash,)
        ).fetchone()
        if not row:
            return error("Invalid device key", 401)
        g.device_mac = row[0]
        return f(*args, **kwargs)
    return decorated
