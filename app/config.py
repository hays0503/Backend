import os


class Config:
    DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(DB_DIR, "sensors.db")
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRES_SEC = 3600
    REFRESH_TOKEN_EXPIRES_SEC = 604800
    KEEP_COUNT_DEFAULT = 1000
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    MIN_PASSWORD_LENGTH = 12
    REQUIRE_PASSWORD_COMPLEXITY = True
    ADMIN_SETUP_ENABLED = True
    SESSION_CLEANUP_AGE_SEC = int(os.environ.get("SESSION_CLEANUP_AGE_SEC", 2592000))
    CORS_ORIGINS = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
