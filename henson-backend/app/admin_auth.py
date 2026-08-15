# -*- coding: utf-8 -*-
"""Shared-password auth for the /admin event-management page.

This is intentionally simple: one shared password (ADMIN_PASSWORD) sent as
an X-Admin-Password header on every /admin/api/* request, checked with a
constant-time comparison. Suited to a small trusted group of event
organizers, not a public product — always serve it over HTTPS in production
since the password travels on every request.
"""
import hmac
import os
from functools import wraps

from flask import jsonify, request

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


def require_admin_password(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not ADMIN_PASSWORD:
            return jsonify({"error": "server misconfigured: ADMIN_PASSWORD is not set"}), 500

        supplied = request.headers.get("X-Admin-Password", "")
        if not hmac.compare_digest(supplied, ADMIN_PASSWORD):
            return jsonify({"error": "invalid admin password"}), 401

        return view(*args, **kwargs)

    return wrapped
