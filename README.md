# Henson Day Backend

Backend API for Henson Day, the University of Maryland campus scavenger hunt: Google-only sign-in (Supabase Auth, UMD email domain restricted), an event schedule with map locations, and per-event AR coin collection with server-verified proximity and points.

The actual project lives in [`henson-backend/`](henson-backend/) — see [`henson-backend/README.md`](henson-backend/README.md) for setup instructions, the API reference, auth flow, and project structure.

## Quick Start

```bash
cd henson-backend
cp .env.example .env   # fill in SUPABASE_URL and SUPABASE_KEY (secret key)
pip install -r requirements.txt
python3 -m flask run
```

Server starts at `http://127.0.0.1:5000`.

## Stack

* **Framework:** Flask
* **Database + Auth:** Supabase (PostgreSQL + Supabase Auth, Google provider)
* **Language:** Python 3.11+
