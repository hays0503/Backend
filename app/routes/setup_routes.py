from flask import Blueprint, request, jsonify
from ..db import seed_admin, get_db

setup_bp = Blueprint("setup", __name__)


@setup_bp.route("/api/setup", methods=["POST"])
def setup_admin():
    db = get_db()
    row = db.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] > 0:
        return jsonify({"error": {"code": "SETUP_COMPLETED",
                                   "message": "Admin already created"}}), 409
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": {"code": "INVALID_BODY",
                                   "message": "Request body must be JSON"}}), 400
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or len(username) < 3:
        return jsonify({"error": {"code": "VALIDATION_ERROR",
                                   "message": "Username is required (min 3 characters)"}}), 400
    created, error = seed_admin(username, password)
    if not created:
        return jsonify({"error": {"code": "SETUP_FAILED", "message": error}}), 400
    return jsonify({"message": f"Admin '{username}' created"}), 201
