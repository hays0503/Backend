import os


class Config:
    DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(DB_DIR, "sensors.db")
    ALEMBIC_INI_PATH = os.path.join(DB_DIR, "alembic.ini")
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
    CORS_ORIGINS = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if o.strip()
    ]
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS = ["Content-Type", "Authorization", "X-Requested-With"]
    CORS_EXPOSE_HEADERS = ["X-Total-Count"]
    CORS_SUPPORTS_CREDENTIALS = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "")
    TEMP_MIN = float(os.environ.get("YESCADA_TEMP_MIN", "-55.0"))
    TEMP_MAX = float(os.environ.get("YESCADA_TEMP_MAX", "125.0"))
    TEMP_COLD_MIN = -10.0
    TEMP_COLD_MAX = 8.0
    TEMP_SAFE_MIN = 8.0
    TEMP_SAFE_MAX = 25.0
    TEMP_WARM_MIN = 25.0
    TEMP_WARM_MAX = 40.0
    TEMP_HOT_MIN = 40.0
    TEMP_DANGER = 55.0
    ALARM_TEMP = 30.0
    ALERT_TEMP = 35.0
    MAX_BATCH_SIZE = int(os.environ.get("YESCADA_MAX_BATCH_SIZE", "500"))
    MAX_KEEP_COUNT = int(os.environ.get("YESCADA_MAX_KEEP_COUNT", "10000"))
    TIMESTAMP_WINDOW_HOURS = int(os.environ.get("YESCADA_TIMESTAMP_WINDOW_HOURS", "24"))
    JWT_ISSUER = os.environ.get("JWT_ISSUER", "yescada-core")
    JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "yescada-api")
    JWT_CLOCK_SKEW_SEC = int(os.environ.get("JWT_CLOCK_SKEW_SEC", "30"))
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per minute")
