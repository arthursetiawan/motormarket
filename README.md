# NegoMotor (repo: motormarket)

**NegoMotor** — jual-beli & lelang motor bekas di Indonesia. Django backend with server-rendered listings, realtime bids (Channels), REST API, and a tabular ML pipeline for sold-price estimates. Django package paths remain `motormarket/` / `market/`.

**Portfolio highlights:** Django + Channels, image uploads/thumbnails, sklearn price intelligence, surat/trust checks, fleet packs, Docker Compose (Postgres + Redis), optional React scaffold under `frontend/`.

## Architecture

```text
motormarket/          Django project (settings, ASGI, URLs)
market/               Models, views, API, WebSocket consumers
templates/ static/    Server UI
ml/ data/ artifacts/  Train → score → model card
frontend/             Optional React + Vite (not required to run the site)
```

| URL | Purpose |
|-----|---------|
| `/` | Home |
| `/market/` | Listings index |
| `/market/motorcycle/<id>/` | Detail + bidding |
| `/market/insights/` | Market / pricing insights + fleet coverage |
| `/market/fleets/` | B2B fleet programs, pack recommendations, inquiries |
| `/api/` | DRF endpoints (pricing, trust, fleet packs) |
| `/admin/` | Django admin |

Agent and editor context: **`AGENTS.md`** (quick index), **`copilot-instructions.md`** (detailed conventions), **`docs/CURSOR.md`** (Cursor workflow).

## Prerequisites

- Python 3.11+
- Node 18+ and npm (only if you work on `frontend/`)
- Docker & Docker Compose (optional)
- Git

## Local setup (virtualenv)

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**Git Bash on Windows / macOS / Linux:** use `source .venv/Scripts/activate` or `source .venv/bin/activate`, and `cp .env.example .env`.

Open http://127.0.0.1:8000/ (admin at `/admin/`).

### Sample data & ML (optional)

```bash
python manage.py seed_market          # if you use seeded listings
python manage.py train_price_model    # trains price_model.joblib
python manage.py score_listings       # scores listings from the model
```

Model documentation: `artifacts/reports/MODEL_CARD.md`.

**Product surfaces (Indonesia fit)**

- Bahasa-first chrome: Lelang / Jual / Armada, estimasi harga, Matic / Bensin
- Listing fair value + deal badges (price model)
- Listing trust score persisted on score (`ListingPrediction.trust_*`); filter listings with `?trust=caution`
- Seller suggested ask on create (`/market/suggest-ask/`, create page panel)
- Fleet pack recommendations + city demand index; inquiries store `pack_snapshot` JSON
- Surat checklist (STNK / BPKB / pajak / plat) + trust score on detail (`ml/trust.py`)
- Deal sheet: meetup + cash/transfer/cicilan intent (no payment gateway)
- Bids must beat current highest
- Bebek segment in `ml/catalog.py` (Supra X, Revo, Jupiter, Vega, Smash…)
- Fleet packs: `exclude_caution` + `ojol_ready` filters
- API: `GET /api/motorcycles/<id>/trust/`, `GET /api/fleets/pack/?program=delivery&size=25&exclude_caution=1&ojol_ready=1`, `GET /api/fleets/coverage/`

**How to verify**

```bash
python manage.py migrate
python manage.py seed_market
python manage.py runserver
# Detail: /market/motorcycle/<id>/ — skor kepercayaan + chip surat + lembar deal
# Fleets: /market/fleets/?program=ride_hailing&exclude_caution=1&ojol_ready=1#pack
python manage.py test market.tests
```

## Environment variables

Copy **`.env.example`** to **`.env`**. Never commit `.env`.

Key variables: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `REDIS_URL`, optional S3 (`USE_S3`, AWS_*). Docker Compose overrides `DATABASE_URL` / Redis for the web container.

## Frontend (React + Vite)

The SPA is optional; the main UX is Django templates.

```bash
cd frontend
npm install
npm run dev
```

Production build: `npm run build` → `frontend/dist`.

## Docker Compose

```bash
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

App: http://localhost:8000

For WebSockets with Redis, ASGI via Daphne:

```bash
daphne -b 0.0.0.0 -p 8000 motormarket.asgi:application
```

## Testing

```bash
python manage.py check
python manage.py test
```

With the dev server running: `curl -I http://127.0.0.1:8000/`

## Cursor / AI setup

1. Open this folder as the workspace root.
2. Select interpreter: `.venv\Scripts\python.exe` (Cursor uses `.vscode/settings.json`).
3. Install recommended extensions when prompted.
4. Copy AI ignore file (keeps chat focused on source, not venv/data blobs):

   ```powershell
   copy .cursorignore.example .cursorignore
   ```

5. Project rules live in **`.cursor/rules/`**:
   - `motormarket-core.mdc` — always on (stack, secrets, definition of done)
   - `django-backend.mdc` — `market/`, templates, static
   - `ml-pipeline.mdc` — `ml/`, train/score, artifacts

Session habit: **Plan** one verifiable outcome → **Agent** implement → run `check` / `test` → update this README if behavior or setup changed. Details: **`docs/CURSOR.md`**.

## Troubleshooting

**allauth `AccountMiddleware`:** ensure `motormarket/settings.py` includes `'allauth.account.middleware.AccountMiddleware'` after `AuthenticationMiddleware`.

**Unresolved Django imports in the editor:** point Cursor/VS Code at the project `.venv` and `pip install -r requirements.txt` into it.

**Changed `SECRET_KEY`:** update `.env`, not committed defaults.

## License

Add a `LICENSE` file when you publish the repo publicly (MIT is a common choice for portfolio projects).
