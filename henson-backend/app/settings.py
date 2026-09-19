
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

