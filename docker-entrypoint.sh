#!/bin/sh
set -e

# Register device API key if env vars are set
if [ -n "$DEVICE_API_KEY" ] && [ -n "$DEVICE_MAC" ]; then
  python /app/scripts/register_device.py || echo "Warning: device registration skipped"
fi

exec python run.py
