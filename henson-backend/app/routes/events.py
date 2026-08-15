# -*- coding: utf-8 -*-
"""Event routes: schedule/map listing, event detail, and coin collection.

GET  /events              full schedule, or one day via ?date=YYYY-MM-DD (for the map)
GET  /events/<event_id>    single event detail (map pin tap)
POST /events/<event_id>/collect   collect this event's coin (proximity-gated)
"""
from datetime import date as date_cls

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from app.auth import require_auth
from app.database import supabase
from app.utils import api_error_payload, haversine_meters

events_bp = Blueprint("events", __name__)

# Client must be within this radius of an event's location to collect its coin.
COLLECT_RADIUS_METERS = 160.934  # 0.1 mile

EVENT_COLUMNS = (
    "id, title, description, location_name, latitude, longitude, "
    "start_time, end_time, points"
)


# GET /events — full schedule; optional ?date=YYYY-MM-DD scopes to one day (map view)
@events_bp.route("/events", methods=["GET"])
@require_auth
def list_events():
    query = supabase.table("events").select(EVENT_COLUMNS).order("start_time")

    date_param = request.args.get("date")
    if date_param:
        try:
            day = date_cls.fromisoformat(date_param)
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
        query = query.gte("start_time", f"{day.isoformat()}T00:00:00+00:00")
        query = query.lte("start_time", f"{day.isoformat()}T23:59:59.999999+00:00")

    try:
        result = query.execute()
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    events = result.data or []

    try:
        collected = (
            supabase.table("event_collections")
            .select("event_id")
            .eq("user_id", g.user_id)
            .execute()
        )
        collected_ids = {row["event_id"] for row in (collected.data or [])}
    except APIError:
        collected_ids = set()

    for event in events:
        event["collected"] = event["id"] in collected_ids

    return jsonify(events), 200


# GET /events/<event_id> — single event detail (map pin tap)
@events_bp.route("/events/<event_id>", methods=["GET"])
@require_auth
def get_event(event_id):
    try:
        result = supabase.table("events").select(EVENT_COLUMNS).eq("id", event_id).execute()
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    rows = result.data or []
    if not rows:
        return jsonify({"error": "event not found"}), 404
    return jsonify(rows[0]), 200


# POST /events/<event_id>/collect — collect this event's coin
@events_bp.route("/events/<event_id>/collect", methods=["POST"])
@require_auth
def collect_event_coin(event_id):
    data = request.get_json(silent=True) or {}
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400
    try:
        user_lat = float(lat)
        user_lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng must be numbers"}), 400

    try:
        already = (
            supabase.table("event_collections")
            .select("id")
            .eq("user_id", g.user_id)
            .eq("event_id", event_id)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502
    if already.data:
        return jsonify({"error": "already collected"}), 409

    try:
        event_res = (
            supabase.table("events")
            .select("id, latitude, longitude, points")
            .eq("id", event_id)
            .execute()
        )
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502
    rows = event_res.data or []
    if not rows:
        return jsonify({"error": "event not found"}), 404
    event = rows[0]

    distance = haversine_meters(user_lat, user_lng, event["latitude"], event["longitude"])
    if distance > COLLECT_RADIUS_METERS:
        return jsonify({"error": "too far away", "distance_meters": round(distance, 1)}), 403

    points = event["points"]
    try:
        supabase.table("event_collections").insert(
            {
                "user_id": g.user_id,
                "event_id": event_id,
                "points_awarded": points,
                "collected_lat": user_lat,
                "collected_lng": user_lng,
                "distance_meters": distance,
            }
        ).execute()
    except APIError as e:
        if api_error_payload(e).get("code") == "23505":
            return jsonify({"error": "already collected"}), 409
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    try:
        profile_res = (
            supabase.table("profiles")
            .select("total_points, events_attended")
            .eq("id", g.user_id)
            .execute()
        )
        profile = (profile_res.data or [{"total_points": 0, "events_attended": 0}])[0]
        updated = (
            supabase.table("profiles")
            .update(
                {
                    "total_points": profile["total_points"] + points,
                    "events_attended": profile["events_attended"] + 1,
                }
            )
            .eq("id", g.user_id)
            .execute()
        )
    except APIError:
        try:
            supabase.table("event_collections").delete().eq("user_id", g.user_id).eq(
                "event_id", event_id
            ).execute()
        except APIError:
            pass
        return jsonify({"error": "failed to update profile; collection rolled back"}), 500

    new_profile = (updated.data or [{}])[0]
    return jsonify(
        {
            "success": True,
            "points_awarded": points,
            "distance_meters": round(distance, 1),
            "total_points": new_profile.get("total_points"),
            "events_attended": new_profile.get("events_attended"),
        }
    ), 201
