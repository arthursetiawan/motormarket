# MotorMarket — agent guide (Cursor / coding agents)

Read this file first when working in this repository.

## What this repo is

Django 4.2 backend for an Indonesian motorcycle bidding marketplace, with optional React + Vite under `frontend/`, WebSockets via Django Channels, and a tabular ML pipeline for sold-price estimates (`ml/` → `artifacts/`).

## Where things live

| Area | Path |
|------|------|
| Project settings & ASGI | `motormarket/` |
| App (models, views, API, consumers) | `market/` |
| Server templates & static | `templates/`, `static/` |
| REST API | `market/api/` |
| ML train/score/recommend | `ml/` |
| Model outputs & model card | `artifacts/` |
| Synthetic training data | `data/` |
| Human + Copilot conventions | `copilot-instructions.md` |
| Cursor workflow | `docs/CURSOR.md` |

## Run locally (Windows-friendly)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

Optional: `python manage.py train_price_model` then `python manage.py score_listings`.

## Rules of engagement

1. **Small diffs** — one user-visible outcome per task; update `README.md` when setup or behavior changes.
2. **Django-native first** — templates, forms, admin, DRF; do not expand the React SPA unless asked.
3. **Migrations** — create and commit when models change.
4. **Secrets** — never commit `.env`, real `SECRET_KEY`, or cloud credentials. Use `.env.example` for keys only.
5. **Tests** — run `python manage.py check` and `python manage.py test` before calling work done.
6. **ML** — paths come from `ml/paths.py`; document metric/limitation changes in `artifacts/reports/MODEL_CARD.md`.

## Cursor project rules

Layered rules live in `.cursor/rules/`:

- `motormarket-core.mdc` — always on (stack, safety, definition of done).
- `django-backend.mdc` — Python/Django/templates in this app.
- `ml-pipeline.mdc` — training, scoring, artifacts.

Prefer **Plan mode** for multi-file features, then **Agent** with a explicit success check (URL + command to verify).
