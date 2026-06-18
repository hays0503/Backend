from flask import Flask
from flask_cors import CORS
from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, origins=config_class.CORS_ORIGINS)

    from .db import init_db, close_db

    init_db()

    app.teardown_appcontext(close_db)

    from .routes.auth_routes import auth_bp
    from .routes.sensor_routes import sensor_bp, device_bp
    from .routes.admin_routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sensor_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(admin_bp)

    return app
