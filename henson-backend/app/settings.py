
# -*- coding: utf-8 -*-
"""Application configuration.

Most configuration is set via environment variables.

For local development, use a .env file to set
environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ]
class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    DEBUG = os.getenv("FLASK_ENV", "production") == "development"
    CORS_ORIGINS = _parse_cors_origins()

    # Optional — set this to a Redis URL (e.g. redis://host:6379/0) once running
    # multiple gunicorn workers, so the cache and rate limiter share state
    # across processes. Without it, both fall back to a per-process in-memory
    # store, which still helps (fewer redundant Supabase reads, still blocks
    # runaway request loops) but isn't perfectly accurate across workers.
    REDIS_URL = os.getenv("REDIS_URL")

    # Caching — GET /events and GET /leaderboard get hit by every signed-in
    # user's app on load/refresh; caching the shared (non-per-user) part of
    # those responses keeps Supabase read load flat as the user count grows.
    CACHE_TYPE = "RedisCache" if REDIS_URL else "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "30"))
    CACHE_REDIS_URL = REDIS_URL

    # Rate limiting — a generous default for normal app usage, with tighter
    # per-route limits on the coin-collect endpoint and the admin API (see
    # app/routes/events.py and app/routes/admin.py).
    RATELIMIT_STORAGE_URI = REDIS_URL or "memory://"
    RATELIMIT_DEFAULT = "60 per minute;1000 per hour"

