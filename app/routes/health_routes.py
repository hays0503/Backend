from flask import Blueprint

from ..db import get_db
from ..responses import error, ok

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.route("/health", methods=["GET"])
def health_check():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        readings_count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        return ok({"status": "ok", "readings_count": readings_count})
    except Exception:
        return error("Service unavailable", 503)
