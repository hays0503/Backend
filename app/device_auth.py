import hashlib
import secrets
from functools import wraps
from flask import request, g
from .db import get_db
from .responses import error


def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def store_api_key(db, controller_mac, plain_key):
    key_hash = hash_api_key(plain_key)
    import time
    now = int(time.time() * 1000)
    db.execute(
        "INSERT OR REPLACE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, ?)",
        (controller_mac, key_hash, now),
    )
    db.commit()


def generate_api_key():
    return "ysd-" + secrets.token_hex(24)


def set_api_key(db, controller_mac):
    plain_key = generate_api_key()
    store_api_key(db, controller_mac, plain_key)
    return plain_key


def remove_api_key(db, controller_mac):
    db.execute(
        "DELETE FROM controller_api_keys WHERE controller_mac = ?",
        (controller_mac,),
    )
    db.commit()


def get_api_key_info(db, controller_mac):
    row = db.execute(
        "SELECT created_at FROM controller_api_keys WHERE controller_mac = ?",
        (controller_mac,),
    ).fetchone()
    if row is None:
        return None
    return {"exists": True, "created_at": row[0]}


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
