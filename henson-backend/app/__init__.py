
"""Main application package."""
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .settings import Config

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)

    # Load config
    app.config.from_object(Config)
    CORS(
        app,
        resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=False,
    )

    # Register blueprints. Each blueprint's routes already include their own
    # leading path segment (e.g. "/events"), so they're mounted with no extra prefix.
    from .routes.users import users_bp
    from .routes.events import events_bp
    from .routes.leaderboard import leaderboard_bp

    app.register_blueprint(users_bp, url_prefix="")
    app.register_blueprint(events_bp, url_prefix="")
    app.register_blueprint(leaderboard_bp, url_prefix="")

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Routes already catch postgrest.exceptions.APIError; this is the backstop
        # for everything else (e.g. Supabase being unreachable) so callers always
        # get JSON instead of a leaked stack trace.
        if isinstance(error, HTTPException):
            return jsonify({"error": error.description}), error.code
        logger.exception("Unhandled error")
        return jsonify({"error": "internal server error"}), 500

    return app

