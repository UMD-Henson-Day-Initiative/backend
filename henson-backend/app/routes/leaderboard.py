# -*- coding: utf-8 -*-
"""Leaderboard route: GET /leaderboard — top 10 players by total points."""
from flask import Blueprint, jsonify
from postgrest.exceptions import APIError

from app.auth import require_auth
from app.database import supabase
from app.extensions import cache
from app.utils import api_error_payload

leaderboard_bp = Blueprint("leaderboard", __name__)


# require_auth runs first on every request (still enforces the JWT check even
# on a cache hit); cache.cached only short-circuits the Supabase query below
# it, and the response isn't personalized so it's safe to share across users.
@leaderboard_bp.route("/leaderboard", methods=["GET"])
@require_auth
@cache.cached(timeout=15, key_prefix="leaderboard")
def get_leaderboard():
    try:
        result = (
            supabase.table("profiles")
            .select("id, first_name, last_name, total_points, events_attended")
            .order("total_points", desc=True)
            .limit(10)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    ranked = [
        {
            "rank": i + 1,
            "user_id": row["id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "total_points": row["total_points"],
            "events_attended": row["events_attended"],
        }
        for i, row in enumerate(result.data or [])
    ]
    return jsonify(ranked), 200
