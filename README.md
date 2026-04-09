# Henson Day Backend (Flask + Supabase)

Backend service for the Henson Day AR/VR application at the University of Maryland. This API powers event discovery, collectible spawning, and analytics for a campus-wide interactive experience.

---

## 🚀 Tech Stack

* **Backend Framework:** Flask
* **Database:** Supabase (PostgreSQL)
* **ORM / Client:** Supabase Python Client + SQLAlchemy (optional)
* **Language:** Python 3.11+

---

## 📁 Project Structure

```
henson-backend/
│
├── app/
│   ├── routes/          # API route blueprints (events, locations, etc.)
│   ├── database.py      # Supabase client + DB connection
│   ├── app.py           # Flask app factory
│
├── autoapp.py           # Entry point
├── requirements.txt
├── .env.example
├── README.md
```

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```
git clone https://github.com/UMD-Henson-Day-Initiative/backend.git
cd backend
```

---

### 2. Create a virtual environment

```
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install dependencies

```
pip install -r requirements.txt
```

---

### 4. Configure environment variables

Copy the example file:

```
cp .env.example .env
```

Fill in the required values:

```
FLASK_APP=autoapp.py
FLASK_ENV=development
FLASK_DEBUG=1

DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/postgres?sslmode=require

SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_KEY=YOUR_ANON_KEY

SECRET_KEY=your-secret-key
```

---

## ▶️ Running the Server

```
python3 -m flask run
```

Server will start at:

```
http://127.0.0.1:5000
```

---

## 🧪 Testing Endpoints

### Health Check

```
curl http://127.0.0.1:5000/health
```

### Example: Get Events

```
curl http://127.0.0.1:5000/events
```

### Pretty Print JSON

```
curl http://127.0.0.1:5000/events | python -m json.tool
```

---

## 🧠 Development Notes

* Use **Blueprints** for modular routes (`app/routes/`)
* Keep database logic inside `database.py`
* Avoid hardcoding secrets — always use `.env`
* Do NOT commit `.env` to GitHub

---

## 📌 Key API Endpoints (Planned)

* `GET /events`
* `GET /locations`
* `GET /collectibles`
* `GET /collectible-spawns`
* `GET /leaderboard`

---

## 🧑‍💻 Team Workflow

1. Pull latest changes:

```
git pull origin main --rebase
```

2. Create a new branch:

```
git checkout -b feature/your-feature-name
```

3. Push changes:

```
git push origin your-branch
```

4. Open a Pull Request

---

## ⚠️ Common Issues

### Flask not found

```
source venv/bin/activate
```

### Supabase URL error

* Ensure `.env` has:

```
SUPABASE_URL=
SUPABASE_KEY=
```

### Port already in use

```
lsof -i :5000
kill -9 <PID>
```

---

## 📈 Future Improvements

* Authentication (Supabase Auth)
* Rate limiting
* Caching layer
* Deployment (Render / Railway / Heroku)

---

## 🎯 Project Goal

Enable a real-time AR/VR campus experience where users can:

* Discover events
* Collect virtual items
* Earn badges
* Compete on leaderboards

---

## 📬 Contact

For questions, reach out to the backend team or open an issue.

---
