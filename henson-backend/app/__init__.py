
"""Main application package."""
from flask import Flask

from .settings import Config

def create_app():
    app = Flask(__name__)
    
    # Load config
    app.config.from_object(Config)

    # Register blueprints
    from .routes.users import users_bp
    from .routes.events import events_bp
    from .routes.collectibles import collectibles_bp
    from .routes.leaderboard import leaderboard_bp

    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(collectibles_bp, url_prefix="/collectibles")
    app.register_blueprint(leaderboard_bp, url_prefix="/leaderboard")

    return app

