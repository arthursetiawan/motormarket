MotorMarket - Online bidding platform for motorcycles (Indonesia)

Overview

This repository contains a starter Django project for MotorMarket (backend) and a React + Vite frontend scaffold under `frontend/`.

This README is continuously updated with the steps required to set up, run, and test the application locally (both using a Python virtualenv and Docker Compose).

Prerequisites

- Python 3.11+ (or the version you prefer)
- Node 18+ and npm (for frontend)
- Docker & Docker Compose (optional — for running Postgres + Redis + web)
- Git

Local setup (recommended: virtual environment)

1. Create and activate a virtual environment

   bash (Git Bash on Windows):
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate
   ```

2. Install Python dependencies

   ```bash
   pip install -r requirements.txt
   ```

   Note: If you plan to use docker-compose, the web service will use the packages installed inside the container. For local development, install them into your venv.

3. Environment variables

   Create a `.env` (or export variables) for local overrides. Example `.env` contents:

   ```env
   SECRET_KEY=replace-me-with-a-secure-secret
   DEBUG=1
   DATABASE_URL=sqlite:///db.sqlite3
   ```

   If running with Docker Compose, `DATABASE_URL` will be provided automatically for the container.

4. Run migrations and create a superuser

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. Run development server

   ```bash
   python manage.py runserver
   ```

   Visit http://127.0.0.1:8000/ to view the site and /admin for Django admin.

Frontend (React + Vite)

1. Initialize the frontend (one-time)

   ```bash
   cd frontend
   npm create vite@latest . --template react
   npm install
   ```

2. Run the frontend dev server (separate terminal)

   ```bash
   npm run dev
   ```

3. Build for production

   ```bash
   npm run build
   ```
   Build artifacts will be in `frontend/dist` (you can serve them with any web server or configure Django to serve static/compiled frontend).

Docker Compose (Postgres + Redis + web)

1. Build and run all services

   ```bash
   docker compose up --build
   ```

2. Inside the web container you still need to run migrations and create a superuser (or do it from host if using volume mounts):

   ```bash
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py createsuperuser
   ```

3. The web app will be exposed on port 8000 (http://localhost:8000)

Testing / Smoke checks

After installing requirements and applying migrations, run these checks locally:

- Django system checks
  ```bash
  python manage.py check
  ```

- Run the test suite
  ```bash
  python manage.py test
  ```

- Quick smoke test (after server is running)
  ```bash
  curl -I http://127.0.0.1:8000/
  ```

Troubleshooting

- allauth.middleware.AccountMiddleware error during migrate:
  If you see: "allauth.account.middleware.AccountMiddleware must be added to settings.MIDDLEWARE", make sure `motormarket/settings.py` includes the middleware line:

  ```python
  'allauth.account.middleware.AccountMiddleware',
  ```

  It should appear after `django.contrib.auth.middleware.AuthenticationMiddleware` in `MIDDLEWARE`.

- Imports unresolved in your editor (like `Import "django..." could not be resolved`): Ensure your editor is using the project virtual environment interpreter. Install dependencies into the venv so language servers can resolve imports.

- If you changed `SECRET_KEY`, update it in your environment or `.env`.

Continuous README updates

I will keep this README up to date as I add features (API endpoints, frontend pages, Docker improvements, Channels for realtime bids, CI). If you want me to run the setup and tests in this workspace now, confirm and I will execute the required commands and report results.
