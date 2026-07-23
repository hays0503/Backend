import os
import uuid
import time as _time
from flask import Flask, g, request
from flask_cors import CORS
from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    if os.environ.get("FLASK_ENV") == "production":
        if not config_class.ADMIN_USERNAME or not config_class.ADMIN_PASSWORD:
            raise RuntimeError(
                "ADMIN_USERNAME and ADMIN_PASSWORD must be set in production."
            )

    CORS(
        app,
        origins=config_class.CORS_ORIGINS,
        methods=getattr(config_class, "CORS_METHODS", ["GET", "POST", "PUT", "DELETE", "OPTIONS"]),
        allow_headers=getattr(config_class, "CORS_ALLOW_HEADERS", ["Content-Type", "Authorization", "X-Requested-With"]),
        expose_headers=getattr(config_class, "CORS_EXPOSE_HEADERS", ["X-Total-Count"]),
        supports_credentials=getattr(config_class, "CORS_SUPPORTS_CREDENTIALS", False),
    )

    import logging
    log_level = getattr(logging, getattr(config_class, "LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_file = getattr(config_class, "LOG_FILE", "")
    if log_file:
        logging.basicConfig(level=log_level, format=log_format, filename=log_file, filemode="a")
    else:
        logging.basicConfig(level=log_level, format=log_format)

    @app.before_request
    def log_request_start():
        g._start_time = _time.monotonic()
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.after_request
    def log_request(response):
        duration_ms = (_time.monotonic() - getattr(g, "_start_time", _time.monotonic())) * 1000
        request_id = getattr(g, "request_id", "-")
        user_id = getattr(g, "user_id", None)
        logging.info(
            "%s | %s %s | user=%s | status=%s | %.1fms",
            request_id,
            request.method,
            request.path,
            user_id or "anonymous",
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    from .db import init_db, seed_admin, close_db

    init_db()
    if config_class.ADMIN_USERNAME and config_class.ADMIN_PASSWORD:
        result = seed_admin(config_class.ADMIN_USERNAME, config_class.ADMIN_PASSWORD)
        if result is not True:
            error = result[1] if isinstance(result, tuple) else "Unknown error"
            logging.warning("Admin seed failed: %s", error)

    app.teardown_appcontext(close_db)

    from .errors import register_error_handlers

    register_error_handlers(app)

    from .routes.auth_routes import auth_bp
    from .routes.sensor_routes import sensor_bp, device_bp
    from .routes.admin_routes import admin_bp
    from .routes.setup_routes import setup_bp
    from .routes.health_routes import health_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sensor_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(health_bp)

    return app
