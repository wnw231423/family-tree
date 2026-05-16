from flask import Flask
from config import Config
from app.db import init_pool, close_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.teardown_appcontext(close_db)

    if app.config.get('INIT_DB_POOL', True):
        with app.app_context():
            init_pool(app)

    from app.routes import routes_bp
    from app.auth import auth_bp
    from app.genealogy import genealogy_bp
    from app.member import member_bp
    from app.query import query_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(genealogy_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(query_bp)

    return app
