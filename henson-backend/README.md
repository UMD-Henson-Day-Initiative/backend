# Henson Day Backend (Flask + Supabase)

Backend API for the Henson Day campus scavenger hunt at the University of Maryland.
Users sign in with a UMD Google account, browse the event schedule and map,
walk to an event's location to collect its coin (points), and compete on a
leaderboard.

---

## Tech Stack

* **Backend Framework:** Flask
* **Database + Auth:** Supabase (PostgreSQL + Supabase Auth, Google provider)
* **Language:** Python 3.11+

---

## Authentication

Sign-in is Google-only, restricted to `@umd.edu` / `@terpmail.umd.edu` accounts,
and happens entirely client-side — this backend never touches a Google
credential directly:

1. The iOS app signs in with Google and calls Supabase's
   `signInWithIdToken(credentials: .init(provider: .google, idToken: ...))`.
2. Supabase Auth creates/looks up the `auth.users` row and returns a session
   JWT (`access_token`).
3. The iOS app sends that token as `Authorization: Bearer <access_token>` on
   every request to this API.
4. `app/auth.py` verifies the JWT against Supabase's JWKS endpoint (derived
   from `SUPABASE_URL` — no separate secret needed) and rejects any request
   whose email isn't a UMD address, even if Supabase considers the session
   valid.
5. The first call to `GET /me` after signing in creates the matching
   `profiles` row (see `supabase/schema.sql`); every call after that just
   returns it.

Signing out is a client-side call to Supabase's `signOut()` — there's no
backend route for it.

### Required setup (Supabase dashboard)

* Enable the **Google** provider under Authentication → Providers.
* Run `supabase/schema.sql` in the SQL editor to create `profiles`, `events`,
  and `event_collections`.

---

## API

All routes below require `Authorization: Bearer <supabase_access_token>`.

### `GET /me`

Returns (creating on first call) the signed-in user's profile:

```json
{
  "id": "...",
  "email": "testudo@umd.edu",
  "first_name": "Testudo",
  "last_name": "Terrapin",
  "total_points": 40,
  "events_attended": 2
}
```

### `GET /events`

Full schedule, ordered by start time. Add `?date=YYYY-MM-DD` to scope to one
day (used by the map screen). Each event includes whether the caller has
already collected its coin:

```json
[
  {
    "id": "...",
    "title": "McKeldin Time Capsule Hunt",
    "description": "...",
    "location_name": "McKeldin Mall",
    "latitude": 38.9869,
    "longitude": -76.9426,
    "start_time": "2026-09-14T18:30:00+00:00",
    "end_time": "2026-09-14T20:00:00+00:00",
    "points": 25,
    "collected": false
  }
]
```

### `GET /events/<event_id>`

Same shape as one item above — used for the map pin detail view.

### `POST /events/<event_id>/collect`

Collects the event's coin. Body: `{"lat": 38.9869, "lng": -76.9426}`.

Validated server-side:

* the caller must be within **0.1 mile (≈160.9 m)** of the event's location
* the same event's coin can only be collected once per user

Responses:

* `201` — `{"success": true, "points_awarded": 25, "distance_meters": 42.1, "total_points": 65, "events_attended": 3}`
* `403` — `{"error": "too far away", "distance_meters": 512.3}`
* `409` — `{"error": "already collected"}`

### `GET /leaderboard`

Top 10 players by total points:

```json
[
  {"rank": 1, "user_id": "...", "first_name": "Testudo", "last_name": "Terrapin", "total_points": 240, "events_attended": 9}
]
```

---

## Admin: managing events

`GET /admin` serves a small password-protected page (no UMD/Google login involved) for non-technical event organizers to add, edit, and delete events — including a click-a-map picker for location, since organizers won't know an event's latitude/longitude off-hand.

* Protected by a single shared password: set `ADMIN_PASSWORD` in `.env`, then open `http://127.0.0.1:5000/admin` (or wherever the backend is deployed) and enter it.
* Anyone with the password can add/edit/delete real events — treat it like any other credential, and always serve it over HTTPS in production (the password travels on every request).
* Under the hood it calls `GET/POST /admin/api/events` and `PATCH/DELETE /admin/api/events/<id>`, each requiring an `X-Admin-Password` header — these are separate from the UMD-auth `/events` routes the iOS app uses, so organizers never need a UMD Google account.

---

## Local Development

```bash
cp .env.example .env   # fill in SUPABASE_URL and SUPABASE_KEY (secret key)
pip install -r requirements.txt
python3 -m flask run
```

Server starts at `http://127.0.0.1:5000`.

```bash
curl http://127.0.0.1:5000/events -H "Authorization: Bearer <token>"
```

---

## Project Structure

```
henson-backend/
├── app/
│   ├── auth.py           # Supabase JWT verification + UMD domain check
│   ├── admin_auth.py     # Shared-password auth for the /admin page
│   ├── database.py       # Supabase client
│   ├── settings.py       # Config from environment variables
│   ├── utils.py          # Shared helpers (haversine distance, error formatting)
│   ├── templates/
│   │   └── admin.html    # Event-management page (password gate + map picker)
│   └── routes/
│       ├── users.py       # GET /me
│       ├── events.py      # GET /events, GET /events/<id>, POST /events/<id>/collect
│       ├── leaderboard.py # GET /leaderboard
│       └── admin.py       # GET /admin, /admin/api/events CRUD
├── supabase/
│   └── schema.sql        # profiles, events, event_collections + RLS
├── autoapp.py            # Entry point
└── .env.example
```
