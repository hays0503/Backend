import sqlite3
from flask import Blueprint
from ..config import Config
from ..responses import ok, error

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.route("/health", methods=["GET"])
def health_check():
    try:
        with sqlite3.connect(Config.DB_PATH, timeout=5) as conn:
            conn.execute("SELECT 1")
        return ok({"status": "ok"})
    except Exception:
        return error("Service unavailable", 503)
