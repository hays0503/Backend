import os


class Config:
    DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(DB_DIR, "sensors.db")
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "change-me-in-production-yescada-2026"
    )
    ACCESS_TOKEN_EXPIRES_SEC = 3600
    REFRESH_TOKEN_EXPIRES_SEC = 604800
    KEEP_COUNT_DEFAULT = 1000
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
