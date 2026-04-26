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

The `alembic/versions/` directory is empty today (Phase 3 is still SQLite-friendly) — generate the first migration with `alembic revision --autogenerate -m "initial"` before the first prod deploy.

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
