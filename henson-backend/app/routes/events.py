from flask import Blueprint, request, jsonify

from app.database import supabase

events_bp = Blueprint("events", __name__)

@events_bp.route("/events", methods=["GET"])
def get_all_events():
    fmt = request.args.get("format")
    res = (
        supabase.table("events")
        .select("*, locations(*)")
        .eq("is_active", True)
        .execute()
    )
    if fmt == "map":
        return jsonify({"format": "map", "events": res.data}), 200
    return jsonify(res.data), 200

@events_bp.route("/events/<event_id>", methods=["GET"])
def get_event_details(event_id):
    res = (
        supabase.table("events")
        .select("*, locations(*), collectibles(*)")
        .eq("id", event_id)
        .execute()
    )
    if not res.data:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(res.data[0]), 200
