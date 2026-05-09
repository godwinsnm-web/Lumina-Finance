# LuminaFinance

Personal-finance dashboard with a Django REST backend and a static-HTML frontend served by Django. SQLite for local dev; flip to MySQL via env vars for production.

## Requirements

- Python 3.10+
- pip

## Setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

From `backend/`:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Demo login

- **Email:** `ada@lumina.local`
- **Password:** `demo1234`

The seed command is idempotent — re-run it anytime to reset the demo user's data.

## Production database (optional)

To run against MySQL instead of SQLite, uncomment `mysqlclient` in `requirements.txt`, install it, then set:

```
DB_ENGINE=django.db.backends.mysql
DB_NAME=luminafinance
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=3306
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=your.domain
```

`schema.sql` at the repo root mirrors the Django models for direct provisioning.

## Layout

```
backend/    Django project (luminafinance) + api app
frontend/   index.html, app.js, styles.css — served as templates/static
schema.sql  Reference SQL schema
```
