import sqlite3
from .config import Config


def get_user_controller_macs(user_id):
    with sqlite3.connect(Config.DB_PATH) as conn:
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
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            f"SELECT id, sensor_address, location, controller_mac FROM sensors WHERE id = ? AND controller_mac IN ({placeholders})",
            (sensor_id, *macs),
        ).fetchone()
    return row
