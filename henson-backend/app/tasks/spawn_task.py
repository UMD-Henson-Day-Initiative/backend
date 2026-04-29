import random
from datetime import datetime, timezone, timedelta
from app.database import supabase

# How long each rarity stays on the map before auto-expiring
RARITY_DESPAWN_MINUTES = {
    "common":    120,
    "rare":      60,
    "epic":      30,
    "legendary": 15,
}

# UMD campus bounding box — spawns placed randomly within these coords
LAT_MIN, LAT_MAX = 38.980, 38.996
LNG_MIN, LNG_MAX = -76.956, -76.934


def _create_random_location_id() -> str | None:
    """Create a location row for a random map point and return its id."""
    lat = round(random.uniform(LAT_MIN, LAT_MAX), 6)
    lng = round(random.uniform(LNG_MIN, LNG_MAX), 6)
    name = f"Random Spawn {lat:.5f}, {lng:.5f}"
    try:
        loc_res = (
            supabase.table("locations")
            .insert(
                {
                    "name": name,
                    "latitude": lat,
                    "longitude": lng,
                    "is_active": True,
                }
            )
            .execute()
        )
    except Exception as e:
        print(f"[spawn_task] Failed to create random location: {e}")
        return None
    rows = loc_res.data or []
    if not rows or not rows[0].get("id"):
        print("[spawn_task] Failed to create random location: missing id")
        return None
    return str(rows[0]["id"])


def expire_overdue_spawns() -> None:
    """
    Marks timed-out active spawns as expired.
    Run frequently (e.g. every 5 minutes) via APScheduler.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        res = (
            supabase.table("collectible_spawns")
            .update({"spawn_status": "expired"})
            .eq("spawn_status", "active")
            .lte("despawn_time", now)
            .execute()
        )
    except Exception as e:
        print(f"[spawn_task] Failed to expire overdue spawns: {e}")
        return

    expired_count = len(res.data or [])
    if expired_count:
        print(f"[spawn_task] Expired {expired_count} overdue spawns at {now}")


def run_hourly_spawns():
    """
    Called every hour by APScheduler.
    Reads spawn_config, checks current active counts per rarity,
    and creates new random spawns up to the configured rate
    without exceeding the max active cap per rarity.
    """
    now = datetime.now(timezone.utc)

    # ── load config ──────────────────────────────────────────────────────────
    try:
        config_res = (
            supabase.table("spawn_config").select("*").order("id").limit(1).execute()
        )
    except Exception as e:
        print(f"[spawn_task] Failed to load config: {e}")
        return

    if not config_res.data:
        print("[spawn_task] No spawn config found — skipping")
        return

    config = config_res.data[0]

    if not config.get("is_active"):
        print("[spawn_task] Spawning is disabled — skipping")
        return

    # ── check current active counts per rarity ───────────────────────────────
    try:
        active_res = supabase.table("collectible_spawns") \
            .select("collectible_id, collectibles(rarity)") \
            .eq("spawn_status", "active") \
            .gt("despawn_time", now.isoformat()) \
            .execute()
    except Exception as e:
        print(f"[spawn_task] Failed to query active spawns: {e}")
        return

    active_counts = {"common": 0, "rare": 0, "epic": 0, "legendary": 0}
    for row in (active_res.data or []):
        rarity = (row.get("collectibles") or {}).get("rarity")
        if rarity in active_counts:
            active_counts[rarity] += 1

    # ── spawn loop ────────────────────────────────────────────────────────────
    spawns_created = 0

    for rarity in ["common", "rare", "epic", "legendary"]:
        rate = config.get(f"rate_{rarity}", 0)
        cap  = config.get(f"max_{rarity}",  0)

        if not rate:
            continue

        # never exceed the cap
        headroom  = max(0, cap - active_counts[rarity])
        to_create = min(rate, headroom)

        if not to_create:
            print(f"[spawn_task] {rarity}: at cap ({active_counts[rarity]}/{cap}) — skipping")
            continue

        # fetch all collectibles of this rarity to pick from
        try:
            pool_res = supabase.table("collectibles") \
                .select("id") \
                .eq("rarity", rarity) \
                .execute()
        except Exception as e:
            print(f"[spawn_task] {rarity}: failed to load pool — {e}")
            continue

        pool = [m["id"] for m in (pool_res.data or []) if m.get("id")]
        if not pool:
            print(f"[spawn_task] {rarity}: no collectibles in DB — skipping")
            continue

        despawn_minutes = RARITY_DESPAWN_MINUTES.get(rarity, 60)

        for _ in range(to_create):
            collectible_id = random.choice(pool)
            despawn_time = (now + timedelta(minutes=despawn_minutes)).isoformat()
            location_id = _create_random_location_id()
            if not location_id:
                continue

            try:
                supabase.table("collectible_spawns").insert({
                    "collectible_id": collectible_id,
                    "location_id":    location_id,
                    "spawn_status":   "active",
                    "spawn_mode":     "random",
                    "spawn_time":     now.isoformat(),
                    "despawn_time":   despawn_time,
                    "max_collectors": 1,
                }).execute()
                spawns_created += 1
            except Exception as e:
                print(f"[spawn_task] Failed to insert {rarity} spawn: {e}")

    print(f"[spawn_task] Done — {spawns_created} new spawns created at {now.isoformat()}")


