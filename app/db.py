import re
import sqlite3
import time
import json
from flask import g
from werkzeug.security import generate_password_hash
from .config import Config


def validate_password_strength(password: str) -> list[str]:
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        errors.append("Password must contain at least one special character")
    return errors


def init_db(db_path=None):
    path = db_path or Config.DB_PATH
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS controllers (
                mac TEXT PRIMARY KEY,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                sensor_count INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_address TEXT NOT NULL UNIQUE,
                controller_mac TEXT NOT NULL REFERENCES controllers(mac),
                location TEXT DEFAULT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id INTEGER NOT NULL REFERENCES sensors(id),
                temperature REAL NOT NULL,
                recorded_at INTEGER NOT NULL,
                UNIQUE(sensor_id, recorded_at)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_sensor_time
            ON readings(sensor_id, recorded_at DESC)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_controllers (
                user_id INTEGER NOT NULL REFERENCES users(id),
                controller_mac TEXT NOT NULL REFERENCES controllers(mac),
                PRIMARY KEY (user_id, controller_mac)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                details TEXT,
                created_at INTEGER NOT NULL
            )
        """)

    return path


def seed_admin(username, password, db_path=None):
    """Create an admin user if no users exist yet.

    Returns (True, None) if the admin was created,
    (False, error_message) if validation fails or users already exist.
    """
    if not username or not password:
        return False, "Username and password are required"
    errors = validate_password_strength(password)
    if errors:
        return False, "; ".join(errors)
    path = db_path or Config.DB_PATH
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] > 0:
            return False, "Users already exist"
        h = generate_password_hash(password)
        now = int(time.time() * 1000)
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (username, h, now),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, 'system', 'admin_seeded', 'user', ?, ?, ?)",
            (user_id, username, json.dumps({"username": username}), now),
        )
    return True, None


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(Config.DB_PATH)
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
