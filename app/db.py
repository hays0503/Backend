import sqlite3
import time
import json
from flask import g
from werkzeug.security import generate_password_hash
from .config import Config


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

        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] == 0:
            h = generate_password_hash("admin")
            now = int(time.time() * 1000)
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                ("admin", h, now),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE username = ?", ("admin",)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, 'system', 'admin_seeded', 'user', 'admin', ?, ?)",
                (user_id, json.dumps({"username": "admin"}), now),
            )

    return path


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
