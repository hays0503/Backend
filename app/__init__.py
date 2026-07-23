from flask import Flask
from flask_cors import CORS
from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if config_class.SECRET_KEY == "change-me-in-production-yescada-2026":
        import os
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError(
                "SECRET_KEY must be changed in production. "
                "Set the SECRET_KEY environment variable."
            )

    if config_class.SECRET_KEY == "change-me-in-production-yescada-2026":
        import os
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError(
                "ADMIN_USERNAME and ADMIN_PASSWORD must be set in production."
            )

    CORS(app, origins=config_class.CORS_ORIGINS)

    from .db import init_db, seed_admin, close_db

    init_db()
    if config_class.ADMIN_USERNAME and config_class.ADMIN_PASSWORD:
        created, error = seed_admin(config_class.ADMIN_USERNAME, config_class.ADMIN_PASSWORD)
        if not created:
            import logging
            logging.warning(f"Admin seed failed: {error}")

    app.teardown_appcontext(close_db)

    from .errors import register_error_handlers

    register_error_handlers(app)

    from .routes.auth_routes import auth_bp
    from .routes.sensor_routes import sensor_bp, device_bp
    from .routes.admin_routes import admin_bp
    from .routes.setup_routes import setup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sensor_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(setup_bp)

    return app
