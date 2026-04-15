from app.routes.users import users_bp
from app.routes.events import events_bp
from app.routes.collectibles import collectibles_bp
from flask import Flask

def create_app():
    app = Flask(__name__)

    app.register_blueprint(users_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(collectibles_bp, url_prefix="/api")

    return app