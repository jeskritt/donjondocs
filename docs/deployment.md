# Deployment

- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [Database setup](#database-setup)
- [Production sketch](#production-sketch)

## Local development

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for testing
cp .env.example .env                  # then edit SECRET_KEY
python main.py                        # http://localhost:8080
```

Tests:

```bash
python -m pytest tests/ -v
python -m pytest tests/ -v --cov
```

## Environment variables

Required:

- `SECRET_KEY` — JWT signing key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Optional (have sane defaults):

- `DATABASE_URL` — default `sqlite+aiosqlite:///./donjondocs.db`. Set to `postgresql+asyncpg://user:pw@host/db` for prod.
- `ALLOW_REGISTRATION` — default `true`. Set `false` to lock down `/register`.
- `ACCESS_TOKEN_EXPIRE_MINUTES` — default `30`.
- `APP_NAME` — default `DonjonDocs`.

## Database setup

Dev: tables auto-create on startup via `Base.metadata.create_all`. The `data/` CSVs auto-ingest if any global table is empty.

Prod (PostgreSQL): manage schema through Alembic when migrations exist:

```bash
alembic upgrade head
python -m app.cli.ingest data/        # one-time global content seed
```

Alembic owns the schema — a baseline migration lives under `alembic/versions/`. Run `alembic upgrade head` before the first prod boot; generate new migrations with `alembic revision --autogenerate -m "..."` only when you change table columns.

### Adding or updating bundled content (a new rule system, gear, etc.)

The startup auto-ingest is an **empty-database bootstrap only**: `main.py` runs the equivalent of
`python -m app.cli.ingest data/` automatically *if and only if* at least one of the six core
global tables (`global_class`, `global_skill`, `global_attribute`, `global_weapon`,
`global_armor`, `global_item`) is empty. Consequently:

- The **first** deploy against a fresh database auto-populates everything in `data/` — no manual step.
- Adding new `data/*.csv` (or new rows/sources — e.g. a new rule system) to a database that is
  **already populated** is **not** picked up automatically. You must run the ingest yourself.

Ingest is idempotent (upsert on `(name, source, owner_id)`), so re-running it is always safe and
never duplicates rows.

**Local dev (SQLite):**

```bash
python -m app.cli.ingest data/
```

**Render production (Supabase Postgres):** run the ingest once against the production database.
Which command you use depends on *where you run it* — the CLI reads `DATABASE_URL` from the
environment:

- **Inside the Render environment** (the **Shell** tab, if your instance tier provides one) — the
  service already has `DATABASE_URL` set, so **no prefix**:

  ```bash
  python -m app.cli.ingest data/
  ```

- **From your local machine**, targeting prod — your local shell defaults to the local SQLite DB,
  so you **must** point it at prod with the connection string prefix (the same pattern used for
  restore rehearsals in `operations.md`). This is the free-tier-friendly option, since the free
  tier has no Shell:

  ```bash
  DATABASE_URL='postgresql+asyncpg://…your-supabase-uri…' python -m app.cli.ingest data/
  ```

> **Supabase tip:** for one-off migrations/ingest, prefer the **direct** connection (port `5432`)
> over the transaction **pooler** (port `6543`) if you hit pooler-related errors. The running web
> service can keep using the pooler.

## Production sketch

Single-process uvicorn behind a reverse proxy is the simplest viable target:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1
```

Notes:

- `--workers > 1` does not work today: NiceGUI's `app.storage.user` is per-process and the rate limiter holds in-process state. To horizontally scale, swap the storage backend and rate limiter to a shared store (Redis) first.
- Tighten `TrustedHostMiddleware` `allowed_hosts` from `["*"]` to your actual hostnames in `main.py` (the `add_middleware(TrustedHostMiddleware, ...)` call).
- Run behind a reverse proxy (nginx/Caddy) terminating TLS. NiceGUI uses WebSockets — proxy must forward `Upgrade` headers.
- Mount `data/` and the SQLite file as persistent volumes if running in a container.

A minimal systemd unit:

```ini
[Service]
WorkingDirectory=/opt/donjondocs
EnvironmentFile=/opt/donjondocs/.env
ExecStart=/opt/donjondocs/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
Restart=always
```
