# -*- coding: utf-8 -*-
"""Supabase Auth JWT verification for Google-only, UMD-only sign-in.

Sign-in itself happens entirely client-side: the iOS app authenticates with
Google via Supabase's GoTrue client (`signInWithIdToken`), and Supabase issues
a session JWT. This module verifies that JWT on every authenticated request
and enforces the UMD email domain restriction — Supabase's Google provider
does not restrict sign-in by email domain, so the backend is the enforcement
point.

Verification uses Supabase's JWKS endpoint (asymmetric ECC/RSA signing keys),
not a shared secret — there is nothing here to leak, and key rotation on
Supabase's side is picked up automatically.
"""
import os
from functools import wraps

import jwt
from flask import g, jsonify, request
from jwt import PyJWKClient

ALLOWED_EMAIL_DOMAINS = ("@umd.edu", "@terpmail.umd.edu")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else None
_jwk_client = PyJWKClient(_JWKS_URL) if _JWKS_URL else None


class AuthError(Exception):
    """Raised when a request's bearer token is missing, invalid, or not a UMD account."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AuthError("missing Authorization: Bearer <token> header")
    token = header[len("Bearer "):].strip()
    if not token:
        raise AuthError("missing Authorization: Bearer <token> header")
    return token


def verify_request() -> dict:
    """Verify the Supabase-issued JWT on the current request and return its claims."""
    if _jwk_client is None:
        raise AuthError("server misconfigured: SUPABASE_URL is not set", 500)

    token = _bearer_token()
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthError("session expired") from e
    except jwt.PyJWTError as e:
        raise AuthError("invalid session token") from e

    email = (claims.get("email") or "").lower()
    if not email.endswith(ALLOWED_EMAIL_DOMAINS):
        raise AuthError("a UMD email (@umd.edu or @terpmail.umd.edu) is required", 403)

    return claims


def require_auth(view):
    """Decorator: verifies the bearer token and sets g.user_id / g.user_email / g.user_claims."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            claims = verify_request()
        except AuthError as e:
            return jsonify({"error": e.message}), e.status
        g.user_id = claims["sub"]
        g.user_email = claims.get("email")
        g.user_claims = claims
        return view(*args, **kwargs)

    return wrapped


def name_from_claims(claims: dict) -> tuple[str, str]:
    """Best-effort (first_name, last_name) from Supabase's Google user_metadata."""
    meta = claims.get("user_metadata") or {}

    given = (meta.get("given_name") or "").strip()
    family = (meta.get("family_name") or "").strip()
    if given or family:
        return given, family

    full = (meta.get("full_name") or meta.get("name") or "").strip()
    if not full:
        return "", ""
    parts = full.split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")
