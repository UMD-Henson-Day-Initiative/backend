
"""Main application package."""
import atexit
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_cors import CORS

from .settings import Config
from .tasks.spawn_task import run_hourly_spawns


def create_app():
    app = Flask(__name__)

    # Load config
    app.config.from_object(Config)
    CORS(
        app,
        resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=False,
    )

    # Register blueprints
    from .routes.users import users_bp
    from .routes.events import events_bp
    from .routes.collectibles import collectibles_bp
    from .routes.leaderboard import leaderboard_bp

    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(collectibles_bp, url_prefix="/collectibles")
    app.register_blueprint(leaderboard_bp, url_prefix="/leaderboard")

    # Hourly random spawns (skip reloader parent so APScheduler is not duplicated in debug)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=run_hourly_spawns,
            trigger="interval",
            hours=1,
            id="hourly_spawns",
            replace_existing=True,
        )
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())

    return app

