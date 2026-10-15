# Copilot Instructions — MotorMarket repository

**Cursor users:** start with `AGENTS.md` and `docs/CURSOR.md`; persistent rules are in `.cursor/rules/*.mdc`.

Purpose

This file tells the automated developer (GitHub Copilot) how to work on this repository so it stays clean, well-documented, and focused on the user's goals: a production-like Django app (MotorMarket) suitable for a portfolio and learning.

Audience

- Primary: the automated developer (you) implementing features.
- Secondary: the human owner (portfolio author) who is learning Django/Python.

Principles

- Keep changes small, well-scoped, and reversible (one feature per branch / PR).
- Document every change in README.md and add short, focused docs where appropriate.
- Prefer Pythonic, Django-native solutions first (Django templates, forms, admin) before adding heavy JS stacks — unless user asks for SPA.
- Provide short, clear instructions to the user on how to run and test locally after each change.

High-level architecture (what the repo contains)

- motormarket/ — Django project settings, ASGI, WSGI, URLs.
- market/ — Django app with models, views, templates, static, forms, consumers, migrations.
- templates/ — Project-level templates (home, base if created).
- static/ — CSS and static assets.
- frontend/ — placeholder for React + Vite app (frontend work lives here when implemented).
- Dockerfile + docker-compose.yml — development & optional production infrastructure (Postgres, Redis, web)
- requirements.txt — Python dependencies
- README.md — living document describing setup and workflow

Major components to maintain and explain to the user

1. Backend (Django)
   - Models: `market.models` (Motorcycle, Bid). Keep models simple and well-documented.
   - Views & Templates: Server-rendered pages for home, listings, detail, create listing, admin.
   - Forms: `market.forms` for safe validation and file uploads.
   - Admin: register models with sensible list_display/search/filters.
   - Migrations: always create and commit migrations when models change.

2. Media & Storage
   - Local dev uses `MEDIA_ROOT` + Django's FileSystemStorage.
   - Production/remote: use S3-compatible storage via `django-storages` + `boto3`. Controlled by `USE_S3` and env variables.
   - Use `sorl-thumbnail` for server-side thumbnails and smaller image payloads.

3. Real-time bidding
   - Channels + Redis channel layer (channels-redis) with ASGI routing.
   - Consumers broadcast bid events to auction-specific groups.
   - WebSocket clients handle live updates; HTTP views still persist bids.

4. Frontend
   - Optional React (Vite) SPA in `frontend/` talking to Django REST API.
   - Until SPA is implemented, keep polished Django templates and minimal JS for progressive enhancement (image previews, websockets).

5. Dev & infra
   - `docker-compose.yml` (Postgres + Redis + web) for reproducible local environment.
   - `Dockerfile` for container image build.
   - Use `daphne` or `uvicorn`/`daphne` when testing Channels behavior; `runserver` is OK for initial dev but not full ASGI concurrency.

Environment variables (document in .env.example)

- SECRET_KEY — required in production
- DEBUG — 0/1
- DATABASE_URL — url, default to sqlite
- USE_S3 — set to 1 to enable S3-compatible storage
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL — for S3/Spaces/Wasabi/MinIO
- REDIS_URL — URL for channel layer (docker-compose uses redis://redis:6379)

Local developer workflow

- Create venv and install requirements:
  python -m venv .venv
  source .venv/Scripts/activate
  pip install -r requirements.txt
- Apply migrations and create sample data / superuser:
  python manage.py migrate
  python manage.py createsuperuser
- Run with Docker Compose (recommended for realistic env):
  docker compose up --build
  docker compose exec web python manage.py migrate
- For Channels testing with Redis, use Daphne:
  daphne -b 0.0.0.0 -p 8000 motormarket.asgi:application

Testing and QA

- Add unit tests for models, forms, views, and websocket consumers.
- Run tests with `python manage.py test` and fix any failures.
- Use `python manage.py check` and `flake8`/`ruff` for linting if added.

Branching & PRs

- Branch naming: feature/<short-desc>, fix/<ticket>, chore/<task>
- One logical change per branch. Include a short description and the testing steps in the PR body.

Documentation rules

- Keep README.md as the high-level living doc (setup, run, demo, quick troubleshooting).
- Create short markdown files for complex subsystems (copilot-instructions.md, STORAGE.md, CHANNELS.md) and link them from README.
- Each new feature that affects developer workflow must update README and add an example `.env.example` entry.

How to write good commit messages

- Title: one-line summary (max 72 chars)
- Body: 1–3 lines explaining why, not what (what is visible in code should be clear)
- Reference migrations or DB changes explicitly

Portfolio guidance (what to highlight)

- Highlight these features in project README and project description on portfolio:
  - Real-time bidding with WebSockets (Channels + Redis).
  - Image uploads + CDN/S3 integration and thumbnails.
  - Clean Django architecture: models, forms, admin, tests.
  - Dockerized development environment.
- Include a short "How I built it" section summarizing major tradeoffs and learning.

Tasks and priorities (short backlog)

1. Finalize media/storage setup (add `.env.example`, README instructions) — high
2. Scope Channels per-auction and secure websocket endpoints — high
3. Add tests for bidding logic and consumers — high
4. Improve listing search, filters, and add facets (make, year) — medium
5. Add pagination caching and thumbnails optimization — medium
6. Scaffold React frontend and connect to DRF — low (unless user requests)
7. CI/CD: add GitHub Actions to run tests and build container — medium

How to request work from the assistant

- Use direct commands like "Implement X in <path>" or "Add tests for market.models.Bid".
- When you want me to run code or commands in your workspace, say "run" or "please run" and I will execute the appropriate commands and report outputs.
- Ask for short diffs or file additions; the assistant will create them and run migrations/tests when requested.

Safety & production notes

- Never commit real secret keys or credentials. Use `.env` and `.gitignore`.
- For production, set DEBUG=0, configure ALLOWED_HOSTS, and set secure storage/CDN.
- Use HTTPS for WebSocket (wss://) in production behind a proper load balancer/proxy.

If the user is unversed in Django

- Always provide a short, non-technical summary of each change added to README (what changed, why it matters, how to test it locally).
- Prefer server-rendered templates and Django forms over complex frontend stacks until the user is comfortable.

Keep this file up to date

- Update `copilot-instructions.md` whenever the project adds a major component (e.g., React frontend, payment integration) or changes the deployment strategy.

---

End of instructions.
