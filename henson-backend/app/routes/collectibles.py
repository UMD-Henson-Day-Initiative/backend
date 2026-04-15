# routes/collectibles.py
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, request, jsonify
from postgrest.exceptions import APIError

from app.database import supabase
from math import radians, sin, cos, sqrt, atan2

collectibles_bp = Blueprint("collectibles", __name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_uuid(value, field_name: str) -> str:
    if value is None or value == "":
        raise ValueError(f"{field_name} is required")
    return str(UUID(str(value)))


def _parse_float(value, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field_name} must be a number") from e


def _api_error_payload(exc: APIError) -> dict:
    if exc.args and isinstance(exc.args[0], dict):
        return exc.args[0]
    return {"message": str(exc)}


# rarity → score for collect flow (DB power_score not used here)
RARITY_SCORES = {
    "common":    10,
    "rare":      25,
    "epic":      50,
    "legendary": 100,
}


# COLLECTIBLES


# GET /collectibles
@collectibles_bp.route("/collectibles", methods=["GET"])
def get_all_collectibles():
    try:
        result = supabase.table("collectibles").select("*").execute()
    except APIError as e:
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502
    return jsonify(result.data), 200


# GET /collectibles/<id>
@collectibles_bp.route("/collectibles/<id>", methods=["GET"])
def get_collectible_by_id(id):
    try:
        _parse_uuid(id, "id")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        result = supabase.table("collectibles").select("*").eq("id", id).execute()
    except APIError as e:
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502
    rows = result.data or []
    if not rows:
        return jsonify({"error": "collectible not found"}), 404
    if len(rows) > 1:
        return jsonify({"error": "multiple collectibles matched"}), 500
    return jsonify(rows[0]), 200


# ─────────────────────────────────────────
# USER COLLECTION
# ─────────────────────────────────────────


# GET /users/<id>/collection
@collectibles_bp.route("/users/<id>/collection", methods=["GET"])
def get_user_collection(id):
    try:
        _parse_uuid(id, "user_id")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        result = (
            supabase.table("user_collectibles")
            .select(
                "*, collectibles(id, muppet_name, muppet_image_url, rarity), collected_at_lat, collected_at_lng"
            )
            .eq("user_id", id)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502
    return jsonify(result.data), 200


# POST /users/<id>/collection — collect a muppet; proximity checked server-side
@collectibles_bp.route("/users/<id>/collection", methods=["POST"])
def collect_muppet(id):
    data = request.get_json()

    if not data or not data.get("collectible_id") or not data.get("lat") or not data.get("lng"):
        return jsonify({"error": "collectible_id, lat, and lng are required"}), 400

    try:
        user_id = _parse_uuid(id, "user_id")
        collectible_id = _parse_uuid(data.get("collectible_id"), "collectible_id")
        user_lat = _parse_float(data.get("lat"), "lat")
        user_lng = _parse_float(data.get("lng"), "lng")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        already_collected = (
            supabase.table("user_collectibles")
            .select("id")
            .eq("user_id", user_id)
            .eq("collectible_id", collectible_id)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502

    if already_collected.data:
        return jsonify({"error": "already collected"}), 409

    try:
        collectible_res = (
            supabase.table("collectibles")
            .select("rarity, event_id, events(locations(latitude, longitude))")
            .eq("id", collectible_id)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502

    rows = collectible_res.data or []
    if not rows:
        return jsonify({"error": "collectible not found"}), 404
    collectible_data = rows[0]

    loc = (collectible_data.get("events") or {}).get("locations")
    if not loc or loc.get("latitude") is None or loc.get("longitude") is None:
        return jsonify({"error": "collectible has no event location"}), 404

    event_lat = loc["latitude"]
    event_lng = loc["longitude"]
    rarity = collectible_data["rarity"]
    if rarity not in RARITY_SCORES:
        return jsonify({"error": f"unknown rarity: {rarity!r}"}), 400
    power_score = RARITY_SCORES[rarity]

    def haversine(lat1, lng1, lat2, lng2):
        R = 6371000
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = haversine(user_lat, user_lng, event_lat, event_lng)

    if distance > 100:
        return jsonify({"error": "too far away", "distance": round(distance, 1)}), 403

    try:
        supabase.table("user_collectibles").insert(
            {
                "user_id":          user_id,
                "collectible_id":   collectible_id,
                "collected_at_lat": user_lat,
                "collected_at_lng": user_lng,
            }
        ).execute()
    except APIError as e:
        if _api_error_payload(e).get("code") == "23505":
            return jsonify({"error": "already collected"}), 409
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502

    ts = _iso_now()
    try:
        existing_score = (
            supabase.table("leaderboard")
            .select("score, collectibles_count")
            .eq("user_id", user_id)
            .execute()
        )
        if existing_score.data:
            supabase.table("leaderboard").update(
                {
                    "score":              existing_score.data[0]["score"] + power_score,
                    "collectibles_count": existing_score.data[0]["collectibles_count"] + 1,
                    "last_updated":       ts,
                }
            ).eq("user_id", user_id).execute()
        else:
            supabase.table("leaderboard").insert(
                {
                    "user_id":            user_id,
                    "score":              power_score,
                    "collectibles_count": 1,
                    "last_updated":       ts,
                }
            ).execute()
    except APIError:
        try:
            supabase.table("user_collectibles").delete().eq("user_id", user_id).eq(
                "collectible_id", collectible_id
            ).execute()
        except APIError:
            pass
        return jsonify({"error": "failed to update leaderboard; collection rolled back"}), 500

    return jsonify(
        {
            "success":     True,
            "distance":    round(distance, 1),
            "power_score": power_score,
            "rarity":      rarity,
        }
    ), 201


# GET /leaderboard
@collectibles_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    if limit < 1:
        return jsonify({"error": "limit must be at least 1"}), 400
    limit = min(limit, 100)

    try:
        result = (
            supabase.table("leaderboard")
            .select("user_id, score, collectibles_count")
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": _api_error_payload(e).get("message", "database error")}), 502

    ranked = []
    for i, row in enumerate(result.data):
        ranked.append(
            {
                "rank":               i + 1,
                "user_id":            row["user_id"],
                "score":              row["score"],
                "collectibles_count": row["collectibles_count"],
            }
        )

    return jsonify(ranked), 200
