import hashlib
import hmac
import logging
import secrets
import time
from functools import wraps

from flask import g, request

from .config import Config
from .db import get_db
from .responses import error

SALT_BYTES = 16
KEY_PREFIX = "ysd-"


def hash_api_key(key, salt=""):
    """SHA-256 of (key + salt). Kept salt-optional for legacy unsalted rows."""
    return hashlib.sha256((key + salt).encode()).hexdigest()


def verify_device_key(plain_key, stored_hash, salt=""):
    """Constant-time comparison. Legacy rows store an unsalted hash (salt='')."""
    if salt:
        computed = hash_api_key(plain_key, salt)
    else:
        computed = hash_api_key(plain_key)
    return hmac.compare_digest(computed, stored_hash)


def generate_api_key():
    """Returns (plain_key, key_hash, salt). Plain key is shown once at issue."""
    raw = secrets.token_bytes(24)
    plain = KEY_PREFIX + raw.hex()
    salt = secrets.token_hex(SALT_BYTES)
    return plain, hash_api_key(plain, salt), salt


def store_api_key(db, controller_mac, plain_key):
    salt = secrets.token_hex(SALT_BYTES)
    key_hash = hash_api_key(plain_key, salt)
    now = int(time.time() * 1000)
    db.execute(
        "INSERT OR REPLACE INTO controller_api_keys "
        "(controller_mac, key_hash, salt, is_active, created_at) "
        "VALUES (?, ?, ?, 1, ?)",
        (controller_mac, key_hash, salt, now),
    )
    db.commit()


def set_api_key(db, controller_mac):
    """Issue or rotate a key. Atomic: replaces the previous row."""
    plain_key, key_hash, salt = generate_api_key()
    now = int(time.time() * 1000)
    db.execute(
        "INSERT OR REPLACE INTO controller_api_keys "
        "(controller_mac, key_hash, salt, is_active, created_at) "
        "VALUES (?, ?, ?, 1, ?)",
        (controller_mac, key_hash, salt, now),
    )
    db.commit()
    return plain_key


def remove_api_key(db, controller_mac):
    """Soft-revoke: keep the row for audit, mark it inactive."""
    now = int(time.time() * 1000)
    db.execute(
        "UPDATE controller_api_keys "
        "SET is_active = 0, revoked_at = ? "
        "WHERE controller_mac = ?",
        (now, controller_mac),
    )
    db.commit()


def get_api_key_info(db, controller_mac):
    row = db.execute(
        "SELECT created_at, is_active, revoked_at FROM controller_api_keys "
        "WHERE controller_mac = ?",
        (controller_mac,),
    ).fetchone()
    if row is None:
        return None
    return {
        "exists": True,
        "created_at": row[0],
        "is_active": bool(row[1]),
        "revoked_at": row[2],
    }


def require_device_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        log_only = getattr(Config, "DEVICE_AUTH_LOG_ONLY", False)

        def accept_log_only(reason):
            if not log_only:
                return None
            logging.warning("device auth log-only: %s accepted", reason)
            return f(*args, **kwargs)

        device_key = request.headers.get("X-Device-Key")
        if not device_key:
            accepted = accept_log_only("missing X-Device-Key header")
            if accepted is not None:
                return accepted
            return error("MISSING_DEVICE_KEY", 401)

        if not request.is_json:
            accepted = accept_log_only("non-JSON request body")
            if accepted is not None:
                return accepted
            return error("MISSING_DEVICE_KEY", 401)
        body = request.get_json(silent=True) or {}
        controller_mac = body.get("controller_mac")
        if not controller_mac:
            accepted = accept_log_only("missing controller_mac")
            if accepted is not None:
                return accepted
            return error("MISSING_DEVICE_KEY", 401)

        conn = get_db()
        row = conn.execute(
            "SELECT key_hash, salt FROM controller_api_keys "
            "WHERE controller_mac = ? AND is_active = 1",
            (controller_mac,),
        ).fetchone()
        if not row or not verify_device_key(device_key, row[0], row[1] or ""):
            accepted = accept_log_only(
                f"invalid device key for controller {controller_mac}"
            )
            if accepted is not None:
                return accepted
            return error("INVALID_DEVICE_KEY", 401)

        g.device_mac = controller_mac
        return f(*args, **kwargs)

    return decorated
