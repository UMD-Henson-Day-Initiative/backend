# -*- coding: utf-8 -*-
"""Admin event management: a small password-protected page + API for
non-technical event organizers to add/edit/delete events.

GET  /admin                    the admin page (password-gated client-side)
GET  /admin/api/events         list all events
POST /admin/api/events         create an event
PATCH  /admin/api/events/<id>  update an event
DELETE /admin/api/events/<id>  delete an event
"""
from flask import Blueprint, jsonify, render_template, request
from postgrest.exceptions import APIError

from app.admin_auth import require_admin_password
from app.database import supabase
from app.utils import api_error_payload

admin_bp = Blueprint("admin", __name__)

EVENT_COLUMNS = (
    "id, title, description, location_name, latitude, longitude, "
    "start_time, end_time, points, created_at, updated_at"
)

REQUIRED_FIELDS = ("title", "location_name", "latitude", "longitude", "start_time", "points")


@admin_bp.route("/admin", methods=["GET"])
def admin_page():
    return render_template("admin.html")


def _parse_event_payload(data: dict, *, partial: bool) -> dict:
    """Validate and coerce a create/update request body. Raises ValueError on bad input."""
    fields = {}

    if "title" in data or not partial:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("title is required")
        fields["title"] = title

    if "description" in data or not partial:
        fields["description"] = (data.get("description") or "").strip()

    if "location_name" in data or not partial:
        location_name = (data.get("location_name") or "").strip()
        if not location_name:
            raise ValueError("location_name is required")
        fields["location_name"] = location_name

    if "latitude" in data or not partial:
        try:
            fields["latitude"] = float(data.get("latitude"))
        except (TypeError, ValueError):
            raise ValueError("latitude must be a number")

    if "longitude" in data or not partial:
        try:
            fields["longitude"] = float(data.get("longitude"))
        except (TypeError, ValueError):
            raise ValueError("longitude must be a number")

    if "start_time" in data or not partial:
        start_time = (data.get("start_time") or "").strip()
        if not start_time:
            raise ValueError("start_time is required")
        fields["start_time"] = start_time

    if "end_time" in data:
        end_time = (data.get("end_time") or "").strip()
        fields["end_time"] = end_time or None

    if "points" in data or not partial:
        try:
            points = int(data.get("points"))
        except (TypeError, ValueError):
            raise ValueError("points must be an integer")
        if points < 0:
            raise ValueError("points must be zero or positive")
        fields["points"] = points

    return fields


# GET /admin/api/events — list all events
@admin_bp.route("/admin/api/events", methods=["GET"])
@require_admin_password
def list_events():
    try:
        result = (
            supabase.table("events")
            .select(EVENT_COLUMNS)
            .order("start_time")
            .execute()
        )
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502
    return jsonify(result.data or []), 200


# POST /admin/api/events — create an event
@admin_bp.route("/admin/api/events", methods=["POST"])
@require_admin_password
def create_event():
    data = request.get_json(silent=True) or {}
    try:
        fields = _parse_event_payload(data, partial=False)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = supabase.table("events").insert(fields).execute()
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    if not result.data:
        return jsonify({"error": "failed to create event"}), 500
    return jsonify(result.data[0]), 201


# PATCH /admin/api/events/<event_id> — update an event
@admin_bp.route("/admin/api/events/<event_id>", methods=["PATCH"])
@require_admin_password
def update_event(event_id):
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "no fields provided"}), 400

    try:
        fields = _parse_event_payload(data, partial=True)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not fields:
        return jsonify({"error": "no valid fields provided"}), 400

    try:
        result = supabase.table("events").update(fields).eq("id", event_id).execute()
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    if not result.data:
        return jsonify({"error": "event not found"}), 404
    return jsonify(result.data[0]), 200


# DELETE /admin/api/events/<event_id> — delete an event (cascades to event_collections)
@admin_bp.route("/admin/api/events/<event_id>", methods=["DELETE"])
@require_admin_password
def delete_event(event_id):
    try:
        result = supabase.table("events").delete().eq("id", event_id).execute()
    except APIError as e:
        return jsonify({"error": api_error_payload(e).get("message", "database error")}), 502

    if not result.data:
        return jsonify({"error": "event not found"}), 404
    return jsonify({"success": True}), 200
