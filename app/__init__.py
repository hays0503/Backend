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

    return app
