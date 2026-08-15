-- Henson Day backend schema (v2)
--
-- Google-only sign-in (via Supabase Auth) + per-event coin collection.
-- Run this against your Supabase project's SQL editor.
--
-- This supersedes the old "muppet spawn" schema. If those tables exist
-- (collectibles, collectible_spawns, spawn_config, user_collectibles,
-- badges, user_badges, locations), they are no longer used by the app
-- and can be dropped once you've confirmed nothing else depends on them:
--
--   drop table if exists user_collectibles cascade;
--   drop table if exists collectible_spawns cascade;
--   drop table if exists spawn_config cascade;
--   drop table if exists user_badges cascade;
--   drop table if exists badges cascade;
--   drop table if exists collectibles cascade;
--   drop table if exists locations cascade;

create extension if not exists "pgcrypto";

-- ── profiles ────────────────────────────────────────────────────────────────
-- One row per authenticated Google account. id matches auth.users.id (the
-- Supabase Auth user created by Google sign-in).
create table if not exists profiles (
    id               uuid primary key references auth.users(id) on delete cascade,
    email            text not null unique,
    first_name       text not null default '',
    last_name        text not null default '',
    total_points     integer not null default 0,
    events_attended  integer not null default 0,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create index if not exists idx_profiles_total_points on profiles (total_points desc);

-- ── events ──────────────────────────────────────────────────────────────────
-- Every scheduled event: where it is, when it is, and how many points its
-- collectible coin is worth.
create table if not exists events (
    id              uuid primary key default gen_random_uuid(),
    title           text not null,
    description     text not null default '',
    location_name   text not null,
    latitude        double precision not null,
    longitude       double precision not null,
    start_time      timestamptz not null,
    end_time        timestamptz,
    points          integer not null default 10,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists idx_events_start_time on events (start_time);

-- ── event_collections ───────────────────────────────────────────────────────
-- One row per (user, event) coin collected. The unique constraint is what
-- enforces "one coin per event per user" server-side.
create table if not exists event_collections (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references profiles(id) on delete cascade,
    event_id         uuid not null references events(id) on delete cascade,
    points_awarded   integer not null,
    collected_lat    double precision not null,
    collected_lng    double precision not null,
    distance_meters  double precision not null,
    collected_at     timestamptz not null default now(),
    unique (user_id, event_id)
);

create index if not exists idx_event_collections_user on event_collections (user_id);
create index if not exists idx_event_collections_event on event_collections (event_id);

-- ── Row Level Security ──────────────────────────────────────────────────────
-- The Flask backend talks to Supabase using the service_role key, which
-- bypasses RLS entirely — these policies are defense-in-depth only, in case
-- the anon key is ever used directly by a client.
alter table profiles enable row level security;
alter table events enable row level security;
alter table event_collections enable row level security;

create policy "profiles_select_own" on profiles
    for select using (auth.uid() = id);

create policy "profiles_update_own" on profiles
    for update using (auth.uid() = id);

create policy "events_select_all" on events
    for select using (true);

create policy "event_collections_select_own" on event_collections
    for select using (auth.uid() = user_id);
