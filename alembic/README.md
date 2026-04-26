# Schema migrations

Alembic owns the schema for this project. `Base.metadata.create_all` is
no longer called at app startup — `alembic upgrade head` is the supported
path for both fresh installs and prod deploys (Render's start command
runs it before booting uvicorn).

## After cloning the repo

```
alembic upgrade head
```

That's it. The DB is now at the latest revision and the app will boot.

## When you change a model

1. Edit `app/models/*`.
2. Generate a migration:
   ```
   alembic revision --autogenerate -m "short imperative description"
   ```
3. **Read the generated file in `alembic/versions/`.** Autogenerate is
   not magic — it misses things like server defaults, check
   constraints, and column type changes (it sees a string change as
   `String(50) → String(100)` but won't notice a Postgres-only enum
   addition without help). Adjust the file in place.
4. Apply locally to verify:
   ```
   alembic upgrade head
   ```
5. Commit the model change and the migration in the **same commit**.

## When you have an existing dev DB created before migrations

If your `donjondocs.db` was created by an old version of the app that
used `Base.metadata.create_all`, you don't need to drop and re-create it.
Just stamp it as up-to-date with the baseline:

```
alembic stamp head
```

This writes the current revision id into the `alembic_version` table
without running any DDL. Future migrations will apply on top.

## Useful commands

```
alembic current              # what revision is the DB at?
alembic history              # show all revisions
alembic downgrade -1         # roll back one revision
alembic downgrade base       # roll all the way back (drops everything)
alembic upgrade <revision>   # jump to a specific revision
```

## Notes

- `env.py` reads `DATABASE_URL` from `app.config.Settings`, so whatever
  is in your `.env` (or env vars) is what migrations target.
- `render_as_batch=True` is set in `env.py` so SQLite `ALTER TABLE`
  works. It's a no-op on Postgres.
- The seeded reference data in `data/*.csv` is loaded at app startup
  by `app.cli.ingest` if the global tables are empty — that is
  separate from migrations and not part of the schema source of truth.
