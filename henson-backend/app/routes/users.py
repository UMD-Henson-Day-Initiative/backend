# -*- coding: utf-8 -*-
"""Profile route: GET /me.

Sign-in and sign-out both happen client-side against Supabase Auth, so there
is no /login or /logout route here. The first authenticated call to /me after
a Google sign-in creates the profile row; every call after that just returns it.
"""
from flask import Blueprint, g, jsonify
from postgrest.exceptions import APIError

from app.auth import name_from_claims, require_auth
from app.database import supabase
from app.utils import api_error_payload

users_bp = Blueprint("users", __name__)

PROFILE_COLUMNS = "id, email, first_name, last_name, total_points, events_attended"


@users_bp.route("/me", methods=["GET"])
@require_auth
def get_my_profile():
    try:
        existing = (
            supabase.table("profiles")
            .select(PROFILE_COLUMNS)
            .eq("id", g.user_id)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    if existing.data:
        return jsonify(existing.data[0]), 200

    first_name, last_name = name_from_claims(g.user_claims)
    try:
        created = (
            supabase.table("profiles")
            .insert(
                {
                    "id": g.user_id,
                    "email": g.user_email,
                    "first_name": first_name,
                    "last_name": last_name,
                }
            )
            .execute()
        )
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "failed to create profile")}), 502

    if not created.data:
        return jsonify({"error": "failed to create profile"}), 500
    return jsonify(created.data[0]), 201
