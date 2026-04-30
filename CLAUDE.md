# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Engineering standards

All work in this repo must adhere to good software engineering practices:

- **Design principles**: SOLID, KISS, DRY, YAGNI. Don't add abstraction the task doesn't need; don't repeat yourself; don't ship anything you can't justify today.
- **Well-documented**: every module, public function/class, and non-obvious schema field has a docstring or short comment explaining *why* (not *what*). The repo's existing "AI Helper Docstring" pattern at the top of each module is the bar — keep it up to date when you change a file.
- **Well-tested**: changes touching `app/services/`, `app/builders/`, `app/schemas/`, or migrations require unit/integration coverage in `tests/`. Run `python -m pytest tests/ -v` before declaring work complete. New behavior without a test is incomplete.
- **Well-architected**:
  - reasonably sized functions and files — split when a function does more than one thing or a file accumulates unrelated concerns
  - organized logically — respect the layer rules below (`models → schemas → services → api/ui`)
  - loosely coupled — UI/API never reach past services into the ORM; services don't import from UI/API
  - no dead code — delete unused imports, helpers, parameters, and feature-flag remnants when their use is gone
  - no deeply nested code or conditional logic — early-return / extract helpers when nesting passes ~3 levels
  - no deeply nested data models — flatten Pydantic structures past 2–3 levels of nesting; prefer composition with named sub-models over anonymous dicts/lists-of-dicts

## Commands

```bash
# Run the app (FastAPI + NiceGUI on :8080, override with $PORT)
python main.py

# Tests (in-memory SQLite, no .env or ingest needed)
python -m pytest tests/ -v
python -m pytest tests/test_builders.py -v             # single file
python -m pytest tests/test_builders.py::test_name -v  # single test
python -m pytest tests/ --cov                          # with coverage

# Schema migrations (alembic is now the source of truth — see "DB schema" below)
alembic upgrade head
alembic revision --autogenerate -m "description"

# Seed / re-ingest the global lookup tables (idempotent; upserts on (name, source, owner_id))
python -m app.cli.ingest data/

# User management
python cli.py create-user --username admin --email a@b.com --password "Pass123!" --role admin
python cli.py list-users
python cli.py reset-password --email a@b.com --new-password "NewPass!"

# Backup / restore user-owned data (users, characters, custom globals).
# Bulk rule data is excluded — re-ingest from data/ CSVs after a restore.
# See docs/operations.md for the JSON format and rehearsal procedure.
python cli.py backup [--output backups/donjondocs-<UTC>.json]
python cli.py restore --input <file> [--mode {merge,replace}] [--dry-run] [--force] [--yes]
```

`requirements.txt` (Python 3.11+, NiceGUI ≥ 3.10) is the only dependency manifest — there is no `pyproject.toml`.

## Architecture

### Layer rules (enforced by convention, not tooling)

```
models  →  schemas  →  services  →  api / ui-pages
                          ↑              ↓
                       (writes)       builders
```

- **`app/models/`** — SQLAlchemy async ORM. Never imports from services or schemas.
- **`app/schemas/`** — Pydantic. Never imports from services. `Character` (in `app/schemas/char_sheet_specific.py`) is the source-of-truth shape for a character.
- **`app/services/`** — owns *all* DB writes and authorization. Both UI pages and API routes go through services; never query the ORM directly from a route or page.
- **`app/api/`** — thin REST routers. Auth via JWT cookie + `app/api/deps.py::get_current_user`.
- **`app/ui/pages/`** — NiceGUI `@ui.page` routes. Auth via `app/ui/middleware.py::AuthMiddleware` (HttpOnly cookie + `app.storage.user`).
- **`app/builders/`** — pure schema → view-model functions. No DB. Trivially unit-testable.

### The character sheet pipeline (the most non-obvious part of the codebase)

A character is stored as a single JSON blob in `characters.character_data`, parsed into the `Character` Pydantic schema. Rendering goes:

```
CharacterRecord.character_data (JSON)
  → Character(**dict)                      # schema
  → get_builder(cs).build()                # → view_data dict, per-style
  → app/ui/components/sheet/*               # @ui.refreshable cards
```

- `app/builders/__init__.py::get_builder()` dispatches on `SheetStyle`. Concrete builders exist for **DND5E, A5E, SHADOWDARK**; the other enum values (`UM5`, `GENEFUNK`, `CARBON`) raise `NotImplementedError`. Style-specific builders override only the methods they need on `BaseSheetBuilder`.
- `app/builders/base.py::_compute_ac()` derives total AC from equipped inventory (armor `base_ac` replaces manual base, `dex_cap` clamps DEX, shields stack). The breakdown is emitted as `view_data['ac_breakdown']`.
- **The "refresh-all" save pattern.** Every `@ui.refreshable` card's refresh handle is collected into `refresh_fns` by `app/ui/pages/character_sheet.py`. The single write path is `_save(updates)` in that file: it calls `update_character()`, rebuilds `state["cs"]` and `state["vd"]`, then iterates `refresh_fns` to re-render every card. This is how an attribute edit propagates to skills/defenses/magic-DC/actions without per-card wiring — **don't add ad-hoc refresh code; just go through `_save`**.
- Inline play-time controls (e.g. exertion +/- in `features_maneuvers.py`, HP +/- and slider in `hp.py`, magic resource +/- in `features_magic.py`) all follow the same shape: an async closure that clamps a value and calls `await _save({field: new_val})`. Use the `render_pm_adjuster(on_delta)` helper in `app/ui/components/sheet/helpers.py` for new +/- pairs.
- Features and Equipment tabs `bind_value()` to the page `state` dict so the active tab survives re-renders.

### Request / middleware order

Stack registered in `main.py` (outermost-listed-first in code, but ASGI runs them in reverse during request and forward during response):

1. `TrustedHostMiddleware` (refuses to boot in non-DEBUG mode if `ALLOWED_HOSTS` is empty/wildcard)
2. `SlowAPIMiddleware` (per-endpoint `@limiter.limit` decorators do the actual policy)
3. `AuthMiddleware` — UI page auth via `app.storage.user`. Public allow-list: `/login`, `/register`, prefixes `/_nicegui`, `/api/`, `/_static`.
4. `SecurityHeadersMiddleware` — registered last so its headers stamp every response, including auth redirects and 429s.

API routes are exempt from `AuthMiddleware` because they carry their own JWT cookie verified by `get_current_user`.

### DB schema, ingest, and Alembic

- Alembic now owns schema (`alembic/versions/2026_04_26_1053-..._baseline_schema.py`). Run `alembic upgrade head` before first boot. The `cli.py` test/dev path still uses `Base.metadata.create_all` for tests.
- On startup, if any of the **six core** global lookup tables (`global_class`, `global_skill`, `global_attribute`, `global_weapon`, `global_armor`, `global_item`) is empty, `app/cli/ingest.py` is auto-invoked against `data/`. The four newer tables (`global_ability`, `global_combat_maneuver`, `global_spell`, `global_destiny`) have ORM definitions but no CSV loader yet — they remain empty until populated manually.
- **Most character state is in the `character_data` JSON blob** — adding a new field to the `Character` Pydantic model usually does *not* require an Alembic migration. Migrations are needed only for changes to the columns of `characters` itself (or other tables).

### Import / export

Versioned envelope: `{"version": 3, "exported_at": ..., "name": ..., "style": ..., "character_data": {...}}`. Import validates `character_data` against `Character`, overrides `owner_id` for safety, and creates a new `CharacterRecord` with a fresh UUID. Endpoints: `GET /api/characters/{id}/export`, `POST /api/characters/import`.

## Conventions worth knowing

- **Three rule systems** (`SheetStyle.DND5E`, `A5E`, `SHADOWDARK`) — feature flags inside builders/cards toggle per-style behavior (e.g. `combat['show_strife']` only true for A5e; Shadowdark suppresses combat maneuvers and prof bonus). Don't hard-code style checks at the UI layer; surface a flag on the view-model.
- **Code references** in docs use `path:line` form. The `docs/` directory is the long-form companion to this file; check `docs/architecture.md` and `docs/database.md` when planning structural changes.
- **State across renders** — when adding a card with a tab/toggle/scroll position the user expects to survive `_save`, bind it into the page `state` dict.
- Tests live in `tests/` and use an async in-memory SQLite. `test_builders.py` and `test_character_service.py` cover the most architecturally-critical paths (schema → view-model and the save flow respectively).
