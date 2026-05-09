from flask import Flask
from config import Config
from app.db import init_pool, close_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_pool(app)

    from app.routes import routes_bp
    app.register_blueprint(routes_bp)

    return app
