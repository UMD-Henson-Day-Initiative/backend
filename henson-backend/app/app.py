from app.routes.users import users_bp
from app.routes.events import events_bp
from app.routes.collectibles import collectibles_bp
from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    CORS(
        app,
        resources={r"/*": {"origins": ["http://127.0.0.1:8080", "http://localhost:8080"]}},
        supports_credentials=False,  # set True only if you use cookies/auth that needs it
    )

    app.register_blueprint(users_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(collectibles_bp, url_prefix="/api")

    return app