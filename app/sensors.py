from .db import get_db


def get_user_controller_macs(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT controller_mac FROM user_controllers WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return [r[0] for r in rows]


def check_sensor_access(sensor_id, user_id):
    macs = get_user_controller_macs(user_id)
    if not macs:
        return None
    placeholders = ",".join("?" for _ in macs)
    conn = get_db()
    row = conn.execute(
        f"SELECT id, sensor_address, location, controller_mac FROM sensors WHERE id = ? AND controller_mac IN ({placeholders})",
        (sensor_id, *macs),
    ).fetchone()
    return row
