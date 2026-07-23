import json
import time
from .db import get_db


def log_action(
    user_id, username, action, target_type=None, target_id=None, details=None
):
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
