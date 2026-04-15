# =============================================================================
# events.py — Events & Locations API
# =============================================================================
#
# This file contains all routes related to locations, events, registrations,
# and attendance tracking for the Henson Day Initiative backend.
#
# All routes are registered on the events_bp Blueprint and mounted at /api
# by create_app() in app.py (e.g. GET /api/locations, POST /api/events/<id>/visit).
#
# ── LOCATIONS ────────────────────────────────────────────────────────────────
#
#   GET  /locations
#        get_all_locations()
#        Returns every active venue on campus. Used to seed the map on load.
#
#   GET  /locations/nearby?lat=&lng=&radius_km=
#        get_nearby_locations()
#        Filters active locations within a radius of the user's GPS position.
#        Uses haversine math in Python. Adds distance_km to each result.
#
#   GET  /locations/search?q=
#        search_locations_by_name()
#        Case-insensitive substring search on location names via SQL ILIKE.
#
#   GET  /locations/<location_id>
#        get_location_by_id()
#        Returns a single location's full details by UUID.
#
# ── EVENTS ───────────────────────────────────────────────────────────────────
#
#   GET  /events
#        get_all_events()
#        Returns all active events with location data joined in one request.
#
#   GET  /events/today
#        get_events_today()
#        Returns active events whose time window overlaps the current UTC day.
#
#   GET  /events/category/<category>
#        get_events_by_category()
#        Filters active events by category enum value (career, club, social…).
#
#   GET  /events/<event_id>
#        get_event_details()
#        Returns full detail for one event regardless of active status.
#
#   GET  /locations/<location_id>/events/upcoming
#        get_upcoming_events_by_location()
#        Returns future events at a specific venue, ordered by start time.
#
# ── REGISTRATIONS ────────────────────────────────────────────────────────────
#
#   POST /events/<event_id>/register
#        register_for_event()
#        Registers a user for an event. Checks active status, capacity, duplicates.
#        Body: { user_id }
#
#   POST /events/<event_id>/unregister
#        unregister_for_event()
#        Removes a user's registration. Confirms it exists before deleting.
#        Body: { user_id }
#
#   GET  /users/<user_id>/registrations
#        get_user_registered_events()
#        Lists all events a user has signed up for with full event + location data.
#
#   GET  /events/<event_id>/registrations/<user_id>
#        is_user_registered_for_event()
#        Returns { registered: bool } — used to toggle Register/Cancel button.
#
# ── VISITS / ATTENDANCE ──────────────────────────────────────────────────────
#
#   POST /events/<event_id>/check-location
#        check_user_at_location()
#        Non-destructive GPS proximity check. Returns { at_location, distance_km }.
#        Body: { lat, lng, radius_km? }
#
#   POST /events/<event_id>/visit
#        log_event_visit()
#        GPS-verified attendance logging. Rejects if user is outside radius (403).
#        On success, upserts event_visits and syncs booth_analytics.
#        Body: { user_id, lat, lng, visit_source?, radius_km? }
#
#   GET  /users/<user_id>/visits
#        get_user_visited_events()
#        Returns a user's full physical attendance history with event + location data.
#
#   GET  /events/<event_id>/visit-count
#        get_event_visit_count()
#        Lightweight visitor count read directly from event_visits.
#
#   GET  /events/<event_id>/booth-traffic
#        get_booth_traffic_summary()
#        Returns aggregated { visit_count, unique_users } from booth_analytics.
#        Always returns a valid shape (zeroed counts if no visits yet).
#
# =============================================================================

from flask import Blueprint, request, jsonify
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timezone

from app.database import supabase

events_bp = Blueprint("events", __name__)

# Default radius used when the caller doesn't specify one.
# 0.05 km = 50 m for attendance checks; 1.0 km for nearby location searches.
_DEFAULT_PROXIMITY_KM = 0.05
_DEFAULT_NEARBY_KM = 1.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance in kilometres between two GPS coordinates
    using the haversine formula. This is the standard approach for calculating
    distances on a sphere and is accurate enough for sub-campus proximity checks.
    R is the Earth's mean radius in km.
    """
    R = 6371.0
    # Convert degree deltas to radians for trig functions
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    # Haversine formula: a is the square of half the chord length
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    # 2 * atan2(sqrt(a), sqrt(1-a)) gives the angular distance in radians; multiply by R for km
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@events_bp.route("/locations", methods=["GET"])
def get_all_locations():
    """
    Returns every location that is currently marked active in the database.
    This is used to populate the campus map on initial load so the frontend
    knows all possible event venues. No parameters are needed — the frontend
    just calls this once and renders all pins. Only locations with is_active=true
    are returned so retired or hidden venues never appear on the map.
    """
    # Pull every active location row — no pagination needed at campus scale
    res = supabase.table("locations").select("*").eq("is_active", True).execute()
    return jsonify(res.data), 200


# NOTE: /locations/nearby and /locations/search must be registered before
# /locations/<location_id> so Flask matches the static path segments first.
# If <location_id> came first, "nearby" and "search" would be treated as UUIDs.

@events_bp.route("/locations/nearby", methods=["GET"])
def get_nearby_locations():
    """
    Returns all active locations within a given radius of the user's current GPS position.
    The frontend passes the device's live lat/lng (obtained from CoreLocation or
    FusedLocationProvider) and an optional radius_km (defaults to 1 km). We fetch all
    active locations from the DB and filter them in Python using the haversine formula,
    which computes great-circle distance on the Earth's surface. Each result includes a
    distance_km field so the frontend can sort or label pins by proximity.

    Query params: lat (required), lng (required), radius_km (optional, default 1.0)
    """
    # Both lat and lng are required — return 400 if either is missing or non-numeric
    try:
        lat = float(request.args["lat"])
        lng = float(request.args["lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "lat and lng query parameters are required and must be numeric"}), 400

    # Fall back to default 1 km radius if not provided by the caller, and validate input
    radius_param = request.args.get("radius_km")
    if radius_param is None or radius_param == "":
        radius_km = _DEFAULT_NEARBY_KM
    else:
        try:
            radius_km = float(radius_param)
        except (TypeError, ValueError):
            return jsonify({"error": "radius_km query parameter must be a positive numeric value"}), 400
        if radius_km <= 0:
            return jsonify({"error": "radius_km query parameter must be a positive numeric value"}), 400

    # Fetch all active locations — we filter in Python since there's no PostGIS RPC set up
    res = supabase.table("locations").select("*").eq("is_active", True).execute()

    # Keep only locations within the radius; attach computed distance for the frontend to display
    nearby = []
    for loc in res.data:
        distance = _haversine_km(lat, lng, loc["latitude"], loc["longitude"])
        if distance <= radius_km:
            nearby.append({**loc, "distance_km": round(distance, 4)})
    return jsonify(nearby), 200


@events_bp.route("/locations/search", methods=["GET"])
def search_locations_by_name():
    """
    Searches active locations whose name contains the given text string, case-insensitively.
    This powers the search bar on the map screen so users can type a building or venue name
    and get matching results instantly. We use Supabase's ilike operator (SQL ILIKE) to do
    a substring match, so partial queries like "iri" will match "Iribe Center". Only active
    locations are searched so stale venues don't pollute results.

    Query params: q (required) — the search string
    """
    # Strip whitespace and reject empty queries immediately
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q query parameter is required"}), 400

    # ilike wraps the term in % wildcards for a contains-anywhere substring match
    res = (
        supabase.table("locations")
        .select("*")
        .eq("is_active", True)
        .ilike("name", f"%{query}%")
        .execute()
    )
    return jsonify(res.data), 200


@events_bp.route("/locations/<location_id>", methods=["GET"])
def get_location_by_id(location_id):
    """
    Fetches the full details of a single location by its UUID. The frontend uses this
    when a user taps a map pin and needs the complete venue info (name, building,
    description, coordinates) to render a detail card. The location_id comes from
    the URL path and must match an existing row in the locations table. Returns 404
    if no matching location is found.

    Path param: location_id (uuid)
    """
    # Filter by primary key — result will be 0 or 1 rows
    res = supabase.table("locations").select("*").eq("id", location_id).execute()

    # res.data is an empty list if the UUID doesn't match any row
    if not res.data:
        return jsonify({"error": "Location not found"}), 404
    return jsonify(res.data[0]), 200


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@events_bp.route("/events", methods=["GET"])
def get_all_events():
    """
    Returns all currently active events with their associated location data joined in.
    This is the primary feed endpoint used to populate the events list or map overlay
    on the home screen. Location data is embedded in each event object via a Supabase
    foreign key join so the frontend gets everything it needs in one request. Only
    events where is_active=true are returned.
    """
    # locations(*) triggers a Supabase FK join — embeds the full location object in each event
    res = (
        supabase.table("events")
        .select("*, locations(*)")
        .eq("is_active", True)
        .execute()
    )
    return jsonify(res.data), 200


# NOTE: /events/today and /events/category/<category> must come before /events/<event_id>
# for the same Flask route-ordering reason as the locations section above.

@events_bp.route("/events/today", methods=["GET"])
def get_events_today():
    """
    Returns all active events that overlap with the current calendar day in UTC.
    The frontend calls this to power a "Today" tab or dashboard widget showing
    what's happening right now on campus. We compute the UTC day boundary at
    midnight and 23:59:59, then filter for events whose window overlaps that range
    (start_time <= day_end AND end_time >= day_start), which correctly catches
    events that started yesterday but are still ongoing.
    """
    # Anchor to current UTC time so the day boundary is consistent regardless of server timezone
    now = datetime.now(timezone.utc)

    # Build ISO 8601 strings for the start and end of today in UTC
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

    # Overlap condition: event must have started before day ends AND must end after day starts
    res = (
        supabase.table("events")
        .select("*, locations(*)")
        .eq("is_active", True)
        .lte("start_time", day_end)   # event starts before or at end of today
        .gte("end_time", day_start)   # event ends at or after start of today
        .execute()
    )
    return jsonify(res.data), 200


@events_bp.route("/events/category/<category>", methods=["GET"])
def get_events_by_category(category):
    """
    Filters and returns all active events that belong to a specific category.
    The frontend uses this to power category filter chips (e.g. "Career", "Social",
    "Workshop") on the events list screen. The category value must match one of the
    valid enum values defined in the event_category type in the database. Location
    data is joined in so no second request is needed to render event cards.

    Path param: category — one of: career, club, academic, social, sports, workshop, other
    """
    # Supabase will reject values that don't match the event_category enum at the DB level
    res = (
        supabase.table("events")
        .select("*, locations(*)")
        .eq("is_active", True)
        .eq("category", category)
        .execute()
    )
    return jsonify(res.data), 200


@events_bp.route("/events/<event_id>", methods=["GET"])
def get_event_details(event_id):
    """
    Returns the full detail record for a single event, including its joined location data.
    The frontend calls this when a user taps an event card to open the event detail screen,
    where they can see the full description, organizer, time window, capacity, and venue.
    Unlike the list endpoints, this always returns the event regardless of is_active status
    so admins or deep-linked users can still view deactivated events. Returns 404 if the
    event UUID does not exist.

    Path param: event_id (uuid)
    """
    # No is_active filter here — detail views should work for inactive events too
    res = supabase.table("events").select("*, locations(*)").eq("id", event_id).execute()

    if not res.data:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(res.data[0]), 200


@events_bp.route("/locations/<location_id>/events/upcoming", methods=["GET"])
def get_upcoming_events_by_location(location_id):
    """
    Returns all future active events scheduled at a specific location, ordered by
    start time ascending. The frontend uses this when a user taps a map pin to show
    what events are coming up at that venue. We filter for start_time >= now so only
    events that haven't started yet are returned, keeping the list relevant. Location
    data is joined in so the full venue object is available in the response.

    Path param: location_id (uuid)
    """
    # Capture current UTC time as ISO string to use as the lower bound for start_time
    now = datetime.now(timezone.utc).isoformat()

    res = (
        supabase.table("events")
        .select("*, locations(*)")
        .eq("location_id", location_id)
        .eq("is_active", True)
        .gte("start_time", now)       # only events that haven't started yet
        .order("start_time")          # ascending so the soonest event is first
        .execute()
    )
    return jsonify(res.data), 200


# ---------------------------------------------------------------------------
# Registrations
# ---------------------------------------------------------------------------

@events_bp.route("/events/<event_id>/register", methods=["POST"])
def register_for_event(event_id):
    """
    Registers a user for a specific event by inserting a row into event_registrations.
    Before inserting, we validate that the event exists and is active, that the event
    hasn't hit its max_capacity (if one is set), and that the user isn't already
    registered to prevent duplicates. The frontend sends this when a user taps the
    "Register" button on an event detail screen.

    Body (JSON): { "user_id": "<uuid>" }
    """
    # Parse body safely — default to empty dict if content-type is wrong or body is absent
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    # Fetch the event to verify it exists and check capacity/active fields
    event_res = supabase.table("events").select("id, max_capacity, is_active").eq("id", event_id).execute()
    if not event_res.data:
        return jsonify({"error": "Event not found"}), 404

    event = event_res.data[0]

    # Prevent registrations for events that have been deactivated by an admin
    if not event.get("is_active"):
        return jsonify({"error": "Event is not active"}), 400

    # Only check capacity if max_capacity is set (null means unlimited)
    max_capacity = event.get("max_capacity")
    if max_capacity is not None:
        # count="exact" asks Supabase to return the row count alongside the data
        count_res = (
            supabase.table("event_registrations")
            .select("user_id", count="exact")
            .eq("event_id", event_id)
            .execute()
        )
        if (count_res.count or 0) >= max_capacity:
            return jsonify({"error": "Event is at full capacity"}), 409

    # Check for a pre-existing registration to avoid duplicate rows
    existing = (
        supabase.table("event_registrations")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("event_id", event_id)
        .execute()
    )
    if existing.data:
        return jsonify({"error": "User is already registered for this event"}), 409

    # All checks passed — insert the registration row
    res = (
        supabase.table("event_registrations")
        .insert({"user_id": user_id, "event_id": event_id})
        .execute()
    )
    return jsonify(res.data[0] if res.data else {}), 201


@events_bp.route("/events/<event_id>/unregister", methods=["POST"])
def unregister_for_event(event_id):
    """
    Removes an existing registration for a user from a specific event. The frontend
    calls this when a user taps "Cancel Registration" on an event they've already
    signed up for. We first confirm the registration exists before attempting the
    delete so we can return a meaningful 404 instead of silently doing nothing.
    Returns a success message on completion.

    Body (JSON): { "user_id": "<uuid>" }
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    # Confirm the registration exists before attempting delete
    existing = (
        supabase.table("event_registrations")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("event_id", event_id)
        .execute()
    )
    if not existing.data:
        return jsonify({"error": "Registration not found"}), 404

    # Delete the specific (user_id, event_id) pair — composite PK ensures only one row is affected
    supabase.table("event_registrations").delete().eq("user_id", user_id).eq("event_id", event_id).execute()
    return jsonify({"message": "Unregistered successfully"}), 200


@events_bp.route("/users/<user_id>/registrations", methods=["GET"])
def get_user_registered_events(user_id):
    """
    Returns all events a specific user has registered for, with full event and location
    data joined in. The frontend uses this to power the user's "My Events" or schedule
    screen, showing every upcoming (and past) event they've signed up for. Registration
    metadata like registered_at is included alongside the full event object so the
    frontend can sort or group by registration date if needed.

    Path param: user_id (uuid)
    """
    # Double-nested join: event_registrations → events → locations, all in one query
    res = (
        supabase.table("event_registrations")
        .select("*, events(*, locations(*))")
        .eq("user_id", user_id)
        .execute()
    )
    return jsonify(res.data), 200


@events_bp.route("/events/<event_id>/registrations/<user_id>", methods=["GET"])
def is_user_registered_for_event(event_id, user_id):
    """
    Checks whether a specific user is currently registered for a specific event and
    returns a simple boolean. The frontend uses this to determine whether to show a
    "Register" or "Cancel Registration" button on the event detail screen. Keeping
    this as a lightweight dedicated endpoint avoids fetching the full registration list
    just to check a single boolean state.

    Path params: event_id (uuid), user_id (uuid)
    Returns: { "registered": true | false }
    """
    # We only need to know if a row exists — select the smallest column to minimise payload
    res = (
        supabase.table("event_registrations")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("event_id", event_id)
        .execute()
    )
    # bool(res.data) is True if at least one row was returned, False if the list is empty
    return jsonify({"registered": bool(res.data)}), 200


# ---------------------------------------------------------------------------
# Visits / Attendance
# ---------------------------------------------------------------------------

@events_bp.route("/events/<event_id>/check-location", methods=["POST"])
def check_user_at_location(event_id):
    """
    Verifies whether the user's current GPS position is within the required proximity
    of an event's venue without logging anything. The frontend can call this as a
    pre-check before showing the "Log Visit" button, giving users live feedback like
    "You are 0.12 km away" if they're not close enough yet. We fetch the event's
    location coordinates from the DB and run a haversine distance calculation against
    the user-supplied lat/lng. The response includes both at_location (bool) and
    distance_km so the frontend can display the exact distance.

    Body (JSON): { "lat": float, "lng": float, "radius_km": float (optional, default 0.05) }
    """
    body = request.get_json(silent=True) or {}

    # Both coordinates are required — without them we can't compute distance
    try:
        user_lat = float(body["lat"])
        user_lng = float(body["lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "lat and lng are required in the request body"}), 400

    # Caller can tighten or loosen the geofence; default is 50 m
    raw_radius = body.get("radius_km", _DEFAULT_PROXIMITY_KM)
    try:
        radius_km = float(raw_radius)
    except (TypeError, ValueError):
        return jsonify({"error": "radius_km must be a number"}), 400
    if radius_km <= 0:
        return jsonify({"error": "radius_km must be positive"}), 400

    # Fetch only the coordinates from the joined location — no need for the full event row
    event_res = (
        supabase.table("events")
        .select("id, locations(latitude, longitude)")
        .eq("id", event_id)
        .execute()
    )
    if not event_res.data:
        return jsonify({"error": "Event not found"}), 404

    # locations is a nested object from the FK join — will be None if location_id is null
    loc = event_res.data[0].get("locations")
    if not loc:
        return jsonify({"error": "Event has no associated location"}), 400

    # Compute straight-line GPS distance between user and the event venue
    distance_km = _haversine_km(user_lat, user_lng, loc["latitude"], loc["longitude"])

    # Return both the boolean gate and the raw distance so the UI can display "X km away"
    return jsonify({"at_location": distance_km <= radius_km, "distance_km": round(distance_km, 4)}), 200


@events_bp.route("/events/<event_id>/visit", methods=["POST"])
def log_event_visit(event_id):
    """
    Logs that a user physically attended an event after verifying their GPS proximity
    server-side. The frontend sends the user's live device coordinates along with their
    user_id, and we compute the haversine distance against the event's stored location —
    if they're outside the required radius we return a 403 with their actual distance so
    the frontend can display a helpful message. On success we upsert into event_visits
    (composite PK prevents duplicate records) and immediately recompute booth_analytics
    so visit_count and unique_users stay accurate in real time.

    Body (JSON): { "user_id": "<uuid>", "lat": float, "lng": float,
                   "visit_source": str (optional, default "gps"),
                   "radius_km": float (optional, default 0.05) }
    """
    body = request.get_json(silent=True) or {}

    # user_id identifies whose attendance record to create
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    # GPS coordinates are mandatory — this endpoint enforces physical presence server-side
    try:
        user_lat = float(body["lat"])
        user_lng = float(body["lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "lat and lng are required to verify your location"}), 400

    # visit_source records how the check-in was triggered (gps, qr, manual, etc.)
    visit_source = body.get("visit_source", "gps")

    # Caller can override the proximity threshold; default is 50 m
    raw_radius = body.get("radius_km", _DEFAULT_PROXIMITY_KM)
    try:
        radius_km = float(raw_radius)
    except (TypeError, ValueError):
        return jsonify({"error": "radius_km must be a numeric value"}), 400
    if radius_km <= 0:
        return jsonify({"error": "radius_km must be a positive value"}), 400

    # Fetch event with its location coords in a single joined query
    event_res = (
        supabase.table("events")
        .select("id, is_active, locations(latitude, longitude)")
        .eq("id", event_id)
        .execute()
    )
    if not event_res.data:
        return jsonify({"error": "Event not found"}), 404

    event = event_res.data[0]

    # Guard against events that have no location assigned
    loc = event.get("locations")
    if not loc:
        return jsonify({"error": "Event has no associated location"}), 400

    # Server-side proximity check — reject with 403 and the actual distance if too far
    distance_km = _haversine_km(user_lat, user_lng, loc["latitude"], loc["longitude"])
    if distance_km > radius_km:
        return jsonify({
            "error": "You must be at the event location to log a visit",
            "distance_km": round(distance_km, 4),
            "required_radius_km": radius_km,
        }), 403

    # Upsert so a user can only have one visit record per event (composite PK enforces uniqueness)
    res = (
        supabase.table("event_visits")
        .upsert(
            {"user_id": user_id, "event_id": event_id, "visit_source": visit_source},
            on_conflict="user_id,event_id",
        )
        .execute()
    )

    # Get accurate counts for analytics using server-side counting to avoid fetching all rows
    visits_res = (
        supabase.table("event_visits")
        .select("user_id", count="exact")
        .eq("event_id", event_id)
        .execute()
    )
    visit_count = visits_res.count or 0
    # With composite PK (user_id,event_id), each row is a unique user visit for this event
    unique_users = visit_count

    # Upsert-style logic: update if an analytics row exists, insert if this is the first visit
    analytics_exists = (
        supabase.table("booth_analytics")
        .select("event_id")
        .eq("event_id", event_id)
        .execute()
    )
    if analytics_exists.data:
        # Row exists — update counts to reflect the latest state
        supabase.table("booth_analytics").update(
            {"visit_count": visit_count, "unique_users": unique_users}
        ).eq("event_id", event_id).execute()
    else:
        # First ever visit for this event — create the analytics row
        supabase.table("booth_analytics").insert(
            {"event_id": event_id, "visit_count": visit_count, "unique_users": unique_users}
        ).execute()

    return jsonify(res.data[0] if res.data else {}), 201


@events_bp.route("/users/<user_id>/visits", methods=["GET"])
def get_user_visited_events(user_id):
    """
    Returns all events a specific user has physically visited, with full event and
    location data joined in. The frontend uses this for a user's attendance history
    screen or to drive gamification features like badges and collectible unlocks that
    are tied to physical presence at events. The visited_at timestamp and visit_source
    are included so the frontend can show when and how each visit was recorded.

    Path param: user_id (uuid)
    """
    # Double-nested join: event_visits → events → locations in one round trip
    res = (
        supabase.table("event_visits")
        .select("*, events(*, locations(*))")
        .eq("user_id", user_id)
        .execute()
    )
    return jsonify(res.data), 200


@events_bp.route("/events/<event_id>/visit-count", methods=["GET"])
def get_event_visit_count(event_id):
    """
    Returns the total number of visit records logged for a specific event by querying
    event_visits directly using an exact count. This is a lightweight alternative to
    the full booth-traffic summary — the frontend can use it to display a simple visitor
    count badge on an event card without loading the full analytics object. Because
    event_visits has a composite PK on (user_id, event_id), this count equals unique
    visitors.

    Path param: event_id (uuid)
    Returns: { "event_id": str, "visit_count": int }
    """
    # count="exact" instructs Supabase to run a COUNT(*) and return it on res.count
    res = (
        supabase.table("event_visits")
        .select("user_id", count="exact")
        .eq("event_id", event_id)
        .execute()
    )
    # res.count can be None if there are zero rows — default to 0
    return jsonify({"event_id": event_id, "visit_count": res.count or 0}), 200


@events_bp.route("/events/<event_id>/booth-traffic", methods=["GET"])
def get_booth_traffic_summary(event_id):
    """
    Returns the aggregated booth analytics record for a specific event, including
    total visit_count and unique_users. This data is maintained in the booth_analytics
    table and kept in sync every time log_event_visit is called. The frontend uses
    this on an organizer or admin dashboard to see how much traffic an event booth
    received. Returns zeroed-out counts (not a 404) if the event has had no visits
    yet, so the frontend always gets a consistent shape to render.

    Path param: event_id (uuid)
    Returns: { "event_id": str, "visit_count": int, "unique_users": int }
    """
    res = (
        supabase.table("booth_analytics")
        .select("*")
        .eq("event_id", event_id)
        .execute()
    )

    # Return a zero-value object rather than 404 so the frontend always gets the same shape
    if not res.data:
        return jsonify({"event_id": event_id, "visit_count": 0, "unique_users": 0}), 200
    return jsonify(res.data[0]), 200
