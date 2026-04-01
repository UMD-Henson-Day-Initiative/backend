from flask import Blueprint, request, jsonify
from app.database import supabase

collectibles_bp = Blueprint("collectibles", __name__) 

# Collectibles
@collectibles_bp.route("/collectibles", methods=["POST"])
def create_collectible():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("rarity") or not data.get("power_score"):
        return jsonify({"error": "name, rarity, and power_score are required"}), 400

    result = supabase.table("collectibles").insert({
        "name":              data.get("name"),
        "rarity":            data.get("rarity"),
        "power_score":       data.get("power_score"),
        "description":       data.get("description"),
        "event_id":          data.get("event_id"),
        "image_url":         data.get("image_url"),
        "model_url":         data.get("model_url"),
        "base_spawn_weight": data.get("base_spawn_weight", 10)
    }).execute()

    return jsonify(result.data[0]), 201

@collectibles_bp.route("/collectibles/<id>", methods=["GET"])
def get_collectible_by_id(id):
    result = supabase.table("collectibles").select("*").eq("id", id).execute()
    return jsonify(result.data[0]), 200

@collectibles_bp.route("/collectibles/rarity/<rarity>", methods=["POST"])
def get_collectible_by_rarity(rarity):
    collectibles = supabase.table("collectibles").select("*").eq("rarity", rarity).execute()
    return jsonify({"Collectibles": collectibles.data}), 200

@collectibles_bp.route("/collectibles/event/<event_id>", methods=["GET"])
def get_collectible_by_event(event_id):
    collectibles = supabase.table("collectibles").select("*").eq("event_id", event_id).execute()
    return jsonify({"Collectibles": collectibles.data}), 200

# Collectible Spawns
# require lat long and radius to be passed in query
@collectibles_bp.route("/spawns/nearby", methods=["GET"])
def get_nearby_collectibles():
    player_lat    = request.args.get("lat")
    player_lng    = request.args.get("lng")
    radius_meters = request.args.get("radius", 200)

    if not player_lat or not player_lng:
        return jsonify({"error": "lat and lng are required"}), 400

    # calls the postgres PostGIS function
    result = supabase.rpc("get_nearby_collectibles", {
        "player_lat":    float(player_lat),
        "player_lng":    float(player_lng),
        "radius_meters": int(radius_meters)
    }).execute()

    return jsonify(result.data), 200

@collectibles_bp.route("/spawns/collect", methods=["POST"])
def collect_item():
    data = request.get_json()
    if not data or not data.get("spawn_id") or not data.get("user_id"):
        return jsonify({"error": "spawn_id and user_id are required"}), 400

    result = supabase.rpc("collect_item", {
        "p_spawn_id": data.get("spawn_id"),
        "p_user_id":  data.get("user_id")
    }).execute()

    return jsonify(result.data), 200
    
@collectibles_bp.route("/spawns/admin", methods=["POST"])
def admin_spawn_collectible():
    data = request.json
    if not data or not data.get("collectible_id") or not data.get("location_id") or not data.get("event_id"):
        return jsonify({"error": "collectible_id, location_id, and event_id are required"}), 400
    
    result = supabase.rpc("admin_spawn_collectible", {
        "p_collectible_id": data.get("collectible_id"),
        "p_location_id":    data.get("location_id"),
        "p_event_id":       data.get("event_id"),
        "p_despawn_after":  data.get("despawn_after", "1 hour"),
        "p_max_collectors": data.get("max_collectors", 1)
    }).execute()

    return jsonify({"spawn_id": result.data}), 201

@collectibles_bp.route("/spawns/random", methods=["POST"])
def create_random_spawn():
    data = request.json
    if not data or not data.get("collectible_id") or not data.get("location_id") or not data.get("despawn_time"):
        return jsonify({"error": "collectible_id, location_id, and despawn_time are required"}), 400

    result = supabase.table("collectible_spawns").insert({
        "collectible_id": data.get("collectible_id"),
        "location_id":    data.get("location_id"),
        "event_id":       data.get("event_id"),
        "despawn_time":   data.get("despawn_time"),
        "spawn_mode":     "random",
        "status":         "active"
    }).execute()
    return jsonify(result.data), 201

@collectibles_bp.route("/spawns/expire", methods=["POST"])
def expire_spawn():
    result = supabase.rpc("expire_stale_spawns").execute()
    return jsonify(result.data), 200

# Drop Schedule
@collectibles_bp.route("/schedule", methods=["POST"])
def create_schedule_drop():
    data = request.get_json()
    if not data or not data.get("collectible_id") or not data.get("event_id") or not data.get("location_id") or not data.get("scheduled_for"):
        return jsonify({"error": "collectible_id, event_id, location_id, and scheduled_for are required"}), 400

    result = supabase.table("drop_schedule").insert({
        "collectible_id": data.get("collectible_id"),
        "event_id":       data.get("event_id"),
        "location_id":    data.get("location_id"),
        "scheduled_for":  data.get("scheduled_for"),
        "despawn_after":  data.get("despawn_after", "30 minutes"),
        "max_collectors": data.get("max_collectors", 1),
        "status":         "pending"
    }).execute()

    return jsonify(result.data[0]), 201


@collectibles_bp.route("/schedule/<id>/cancel", methods=["PUT"])
def cancel_schedule_drop(id):
    result = supabase.table("drop_schedule").update({"status": "expired"}).eq("id", id).eq("status", "pending").execute()
    return jsonify(result.data), 200

@collectibles_bp.route("/schedule/pending", methods=["GET"])
def get_scheduled_drops():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    result = supabase.table("drop_schedule") \
        .select("*") \
        .eq("status", "pending") \
        .lte("scheduled_for", now) \
        .execute()

    return jsonify(result.data), 200

@collectibles_bp.route("/schedule/<id>/spawned", methods=["PUT"])
def mark_drop_as_spawned(id):
    result = supabase.table("drop_schedule").update({"status": "spawned"}).eq("id", id).execute()
    return jsonify(result.data), 200

@collectibles_bp.route("/schedule/event/<event_id>", methods=["GET"])
def get_scheduled_drops_by_event(event_id):
    result = supabase.table("drop_schedule") \
        .select("*, collectibles(name, rarity)") \
        .eq("event_id", event_id) \
        .order("scheduled_for", desc=False) \
        .execute()

    return jsonify(result.data), 200

# Leaderboard
@collectibles_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    limit = int(request.args.get("limit", 10))

    result = supabase.table("leaderboard") \
        .select("user_id, score, collectibles_count, profiles(username)") \
        .order("score", desc=True) \
        .limit(limit) \
        .execute()

    return jsonify(result.data), 200

@collectibles_bp.route("/leaderboard/<user_id>", methods=["GET"])
def get_user_rank(user_id):
    result = supabase.rpc("get_user_rank", {
        "p_user_id": user_id
    }).execute()

    return jsonify(result.data), 200

@collectibles_bp.route("/leaderboard/score", methods=["POST"])
def increment_user_score():
    data = request.json
    
    if not data or not data.get("user_id") or not data.get("power_score"):
        return jsonify({"error": "user_id and power_score are required"}), 400

    result = supabase.rpc("increment_user_score", {
        "p_user_id": data.get("user_id"),
        "p_power_score": data.get("power_score")
    }).execute()

    return jsonify(result.data), 200

@collectibles_bp.route("/leaderboard/refresh", methods=["POST"])
def refresh_leaderboard():
    result= supabase.rpc("refresh_leaderboard").execute()
    return jsonify(result.data), 200