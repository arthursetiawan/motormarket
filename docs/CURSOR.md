# Cursor workflow for MotorMarket

Use this repo as a **portfolio factory**: each session should end with something a visitor can run or click.

## One-time setup in Cursor

1. Open the `motormarket` folder as the workspace root (not a parent directory).
2. Select the interpreter: **`.venv\Scripts\python.exe`** (VS Code/Cursor will suggest it after you create the venv).
3. Install recommended extensions when prompted (`.vscode/extensions.json`).
4. Copy env and ignore files:
   ```powershell
   copy .env.example .env
   copy .cursorignore.example .cursorignore
   ```
5. Project rules load automatically from `.cursor/rules/`. `AGENTS.md` is the short index.

## Session loop

| Step | Mode | What to do |
|------|------|------------|
| 1 | **Plan** | Describe one outcome + how to verify (URL, command, screenshot). |
| 2 | **Agent** | Implement; point at files (`market/views.py`, templates, etc.). |
| 3 | **You** | Review the diff; run check/tests. |
| 4 | **Agent (optional)** | “Update README with what changed and how to verify.” |
| 5 | **Git** | Commit when *you* ask; push for portfolio visibility. |

Start a **new chat** per feature. Long threads drift from project rules.

## Prompt templates

**Feature**

> Plan: Add [X] on `/market/...`. Success = [behavior]. Keep Django templates; no new npm deps. Read `AGENTS.md`.

**Bug**

> On `/market/...`, [actual] vs [expected]. Repro steps: … Fix with minimal diff; add a test if missing.

**ML**

> Retrain with `train_price_model`, update scores, refresh `MODEL_CARD.md` limitations if features changed.

**Portfolio polish**

> Add a README section “Architecture” with 3 bullets and one design tradeoff I made. No marketing fluff.

## Rules map

| File | When it applies |
|------|-----------------|
| `motormarket-core.mdc` | Every chat |
| `django-backend.mdc` | Python, templates, static |
| `ml-pipeline.mdc` | `ml/`, train/score commands, artifacts |

Edit rules when the stack changes (e.g. you make React the primary UI).

## Personal rules (Cursor Settings)

Consider adding **user** rules (not in this repo) for all portfolio projects:

- README must include setup, test command, and one architecture decision.
- Never commit secrets; use `.env.example`.
- Commits only when I explicitly ask.

## Parallel work

Safe to run a second agent on **docs/tests** while you implement in the main chat—avoid two agents editing the same files.

## Checklist before you push

- [ ] `python manage.py check`
- [ ] `python manage.py test`
- [ ] README updated if behavior or setup changed
- [ ] No `.env` or sqlite DB in the commit
- [ ] Screenshot or demo path noted in README (optional but strong for GitHub)
