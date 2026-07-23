import os
from flask import Flask
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

    CORS(app, origins=config_class.CORS_ORIGINS)

    import logging
    import time as _time

    @app.before_request
    def log_request_start():
        g._start_time = _time.time()

    @app.after_request
    def log_request(response):
        duration = _time.time() - getattr(g, '_start_time', _time.time())
        logging.info(
            f"{request.method} {request.path} {response.status_code} {duration:.3f}s"
        )
        return response

    from .db import init_db, seed_admin, close_db

    init_db()
    if config_class.ADMIN_USERNAME and config_class.ADMIN_PASSWORD:
        result = seed_admin(config_class.ADMIN_USERNAME, config_class.ADMIN_PASSWORD)
        if result is not True:
            import logging
            error = result[1] if isinstance(result, tuple) else "Unknown error"
            logging.warning(f"Admin seed failed: {error}")

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
