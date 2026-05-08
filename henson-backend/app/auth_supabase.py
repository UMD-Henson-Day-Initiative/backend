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

Signing:
  - Many projects use HS256 with the JWT Secret (SUPABASE_JWT_SECRET).
  - Some use RS256/ES256; verify via JWKS at:
    <SUPABASE_URL>/auth/v1/.well-known/jwks.json
"""

from __future__ import annotations

import ssl
from functools import wraps

import certifi
import jwt
from jwt import PyJWKClient, PyJWKClientConnectionError
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


def _decode_supabase_access_token(token: str) -> dict:
    """Verify Supabase Auth access_token (HS256 secret or RS256/ES256 JWKS)."""
    aud = (current_app.config.get("SUPABASE_JWT_AUDIENCE") or "authenticated").strip()
    secret = (current_app.config.get("SUPABASE_JWT_SECRET") or "").strip()
    base_url = (current_app.config.get("SUPABASE_URL") or "").rstrip("/")
    issuer = f"{base_url}/auth/v1" if base_url else None

    header = jwt.get_unverified_header(token)
    alg = (header.get("alg") or "HS256").upper()

    decode_kw: dict = {
        "algorithms": [alg],
        "audience": aud,
    }
    if issuer:
        decode_kw["issuer"] = issuer

    if alg == "HS256":
        if not secret:
            raise jwt.InvalidTokenError("HS256 tokens require SUPABASE_JWT_SECRET")
        return jwt.decode(token, secret, **decode_kw)

    if alg in ("RS256", "ES256"):
        if not base_url:
            raise jwt.InvalidTokenError(f"{alg} tokens require SUPABASE_URL for JWKS lookup")
        jwks_url = f"{base_url}/auth/v1/.well-known/jwks.json"
        # Use certifi's CA bundle: macOS python.org builds often lack a working default store.
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        jwk_client = PyJWKClient(jwks_url, ssl_context=ssl_ctx)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, **decode_kw)

    raise jwt.InvalidTokenError(f"Unsupported JWT alg: {alg}")


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

        try:
            payload = _decode_supabase_access_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except PyJWKClientConnectionError as e:
            return jsonify({"error": f"Could not reach Supabase JWKS (check SSL / SUPABASE_URL): {e!s}"}), 503
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid token: {e!s}"}), 401

        if not _is_admin_payload(payload):
            return jsonify({"error": "Admin privileges required (app_metadata.admin or ADMIN_EMAILS)"}), 403

        return fn(*args, **kwargs)

    return wrapper
