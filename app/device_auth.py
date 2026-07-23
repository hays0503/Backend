import hashlib
import secrets
import time
from functools import wraps
from flask import request, g
from .db import get_db
from .responses import error


def generate_api_key():
    return secrets.token_hex(32)


def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def store_api_key(mac, key):
    key_hash = hash_api_key(key)
    conn = get_db()
    now = int(time.time() * 1000)
    conn.execute(
        "INSERT OR REPLACE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, ?)",
        (mac, key_hash, now),
    )


def revoke_api_key(mac):
    conn = get_db()
    conn.execute("DELETE FROM controller_api_keys WHERE controller_mac = ?", (mac,))


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
