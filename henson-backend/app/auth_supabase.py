"""
Verify Supabase Auth access tokens (JWT) for admin-only Flask routes.

Supabase setup (Dashboard):
  1) Project Settings → API:
     - Project URL → SUPABASE_URL (already used by backend)
     - anon public → SUPABASE_ANON_KEY (safe for /admin bootstrap + browser login)
     - JWT Secret → SUPABASE_JWT_SECRET (server-only; never expose to frontend)
  2) Authentication → Providers: enable Email (or your chosen provider).
  3) Create an admin user (Authentication → Users → Add user) with a password.
  4) Grant admin access using ONE of:
     a) SQL Editor (example; replace email):
        update auth.users
        set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"admin": true}'::jsonb
        where email = 'you@example.com';
     b) Or set env ADMIN_EMAILS=comma,separated,emails (lowercase match on JWT email claim)

JWT access tokens use aud="authenticated" and iss="<SUPABASE_URL>/auth/v1" by default.
"""

from __future__ import annotations

from functools import wraps

import jwt
from flask import current_app, jsonify, request


def _bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _admin_email_allowlist() -> set[str]:
    raw = (current_app.config.get("ADMIN_EMAILS") or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _is_admin_payload(payload: dict) -> bool:
    app_meta = payload.get("app_metadata") or {}
    if app_meta.get("admin") is True:
        return True
    email = (payload.get("email") or "").strip().lower()
    if email and email in _admin_email_allowlist():
        return True
    return False


def require_supabase_jwt(fn):
    """
    Require a valid Supabase access JWT (Bearer) and admin privileges.

    If SUPABASE_JWT_SECRET is unset and Flask debug is on, the check is skipped
    (local convenience). In production, set SUPABASE_JWT_SECRET.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        secret = (current_app.config.get("SUPABASE_JWT_SECRET") or "").strip()
        if not secret:
            if current_app.debug:
                return fn(*args, **kwargs)
            return jsonify({"error": "Server auth not configured (set SUPABASE_JWT_SECRET)"}), 503

        token = _bearer_token()
        if not token:
            return jsonify({"error": "Missing Authorization: Bearer <access_token>"}), 401

        aud = (current_app.config.get("SUPABASE_JWT_AUDIENCE") or "authenticated").strip()
        base_url = (current_app.config.get("SUPABASE_URL") or "").rstrip("/")
        issuer = f"{base_url}/auth/v1" if base_url else None

        try:
            decode_kwargs: dict = {
                "algorithms": ["HS256"],
                "audience": aud,
            }
            if issuer:
                decode_kwargs["issuer"] = issuer
            payload = jwt.decode(token, secret, **decode_kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid token: {e!s}"}), 401

        if not _is_admin_payload(payload):
            return jsonify({"error": "Admin privileges required (app_metadata.admin or ADMIN_EMAILS)"}), 403

        return fn(*args, **kwargs)

    return wrapper
