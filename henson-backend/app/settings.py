
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
        "http://127.0.0.1:5000",
        "http://localhost:5000",
    ]
class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    # Public anon key (Dashboard → Settings → API → anon public). Used only by /admin bootstrap for browser login.
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    # Dashboard → Settings → API → JWT Secret (server-only). When set, spawn admin routes require Bearer JWT.
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
    SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    # Comma-separated admin emails (lowercase) if you do not use app_metadata.admin on the user.
    ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    DEBUG = os.getenv("FLASK_ENV", "production") == "development"
    CORS_ORIGINS = _parse_cors_origins()

