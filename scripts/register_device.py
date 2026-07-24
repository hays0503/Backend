#!/usr/bin/env python3
"""Register a device controller and API key at startup."""

import os
import sys
import time

sys.path.insert(0, "/app")

from app import create_app
from app.db import get_db
from app.device_auth import hash_api_key

device_mac = os.environ.get("DEVICE_MAC")
device_key = os.environ.get("DEVICE_API_KEY")

if not device_mac or not device_key:
    print("DEVICE_MAC/DEVICE_API_KEY not set, skipping registration")
    sys.exit(0)

app = create_app()
with app.app_context():
    db = get_db()
    now = int(time.time() * 1000)
    db.execute(
        "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) VALUES (?, ?, ?, 0)",
        (device_mac, now, now),
    )
    db.execute(
        "INSERT OR REPLACE INTO controller_api_keys (controller_mac, key_hash, created_at) VALUES (?, ?, ?)",
        (device_mac, hash_api_key(device_key), now),
    )
    db.commit()
    print(f"Device registered: MAC={device_mac}")
