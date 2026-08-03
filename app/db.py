import os
import re
import sqlite3
import time
import json
from flask import g
from werkzeug.security import generate_password_hash
from alembic.config import Config as AlembicConfig
from alembic import command
from .config import Config


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        return False, "Password must contain at least one special character"
    return True, None


def run_migrations(db_path=None):
    """Apply Alembic migrations to the database.

    New/empty databases run ``upgrade head`` to build the schema.
    Existing legacy databases (tables present but no ``alembic_version``)
    are stamped at head so their data is never touched.
    """
    path = db_path or Config.DB_PATH
    alembic_cfg = AlembicConfig(Config.ALEMBIC_INI_PATH)
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path}")

    tables = set()
    if os.path.exists(path):
        try:
            with sqlite3.connect(path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
        except sqlite3.Error:
            tables = set()

    if "controllers" in tables and "alembic_version" not in tables:
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")
    return path


def init_db(db_path=None):
    """Idempotent schema bootstrap (legacy-compatible name).

    Equivalent to :func:`run_migrations`; kept so existing callers
    (tests, startup path) keep working.
    """
    return run_migrations(db_path)


def seed_admin(username, password, db_path=None):
    """Create an admin user if no users exist yet.

    Returns True if the admin was created,
    (False, error_message) if validation fails or users already exist.
    """
    if not username or not password:
        return False, "Username and password are required"
    ok, msg = validate_password_strength(password)
    if not ok:
        return False, msg
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
    return True


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(Config.DB_PATH)
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.commit()
        db.close()
