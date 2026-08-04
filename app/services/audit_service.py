import json
import time

from ..db import get_db


def log_action(user_id, username, action, target_type=None, target_id=None, details=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            username,
            action,
            target_type,
            target_id,
            json.dumps(details) if details else None,
            int(time.time() * 1000),
        ),
    )


def get_audit_log(limit, offset):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    rows = conn.execute(
        "SELECT id, user_id, username, action, target_type, target_id, details, created_at FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    logs = []
    for (
        log_id,
        user_id,
        username,
        action,
        target_type,
        target_id,
        details,
        created_at,
    ) in rows:
        try:
            parsed_details = json.loads(details) if details else None
        except (json.JSONDecodeError, TypeError):
            parsed_details = {"_raw": details, "_error": "corrupt_json"}
        logs.append(
            {
                "id": log_id,
                "user_id": user_id,
                "username": username,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "details": parsed_details,
                "created_at": created_at,
            }
        )
    return {"logs": logs, "total": total, "limit": limit, "offset": offset}
