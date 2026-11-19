# Development

- [CLI reference](#cli-reference)
- [Running tests](#running-tests)
- [Data ingestion](#data-ingestion)
- [Database migrations](#database-migrations)

## CLI reference

### User management

```bash
python cli.py list-users
python cli.py create-user --username <name> --email <email> --password "<pass>" --role <admin|premium|standard>
python cli.py reset-password --email <email> --new-password "<pass>"
```

### Data ingestion

```bash
# Full ingest from bundled data
python -m app.cli.ingest data/

# Ingest a single directory (e.g. custom homebrew CSVs)
python -m app.cli.ingest path/to/custom/
```

Re-running is safe — it upserts by `(name, source, owner_id)`.

This populates the global lookup tables. `app/cli/ingest.py` currently has CSV loaders for the six core tables; the four others have ORM definitions ready but no loader yet:

| Table | Contents | Loader |
|-------|----------|--------|
| `global_weapon` | Weapons for all supported systems | ✓ |
| `global_armor` | Armor for all supported systems (parses `base_ac` / `dex_cap` / `is_shield` from CSV) | ✓ |
| `global_item` | Adventuring gear | ✓ (CSV files prefixed `equipment`) |
| `global_class` | Class definitions | ✓ |
| `global_skill` | Skill definitions | ✓ |
| `global_attribute` | Ability score definitions | ✓ |
| `global_ability` | Class/race features and feats | pending |
| `global_combat_maneuver` | A5e maneuvers | pending |
| `global_spell` | Spells | pending |
| `global_destiny` | A5e destinies | pending |

The startup hook in `main.py` only triggers an auto-ingest when the six core tables are empty — the four "pending" tables won't block startup if they're empty.

### Database migrations

```bash
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "description"  # create a new migration
```

The `alembic/versions/` directory is currently empty — the dev SQLite database is created at startup via `Base.metadata.create_all`. Alembic becomes the system of record when moving to PostgreSQL.

## Running tests

```bash
nox                                         # clean-venv unit/integration tests (CI runs this)
nox -s e2e                                  # opt-in Playwright browser E2E suite (tests/e2e/)
python -m pytest tests/ -v                  # fast local unit/integration tests (skips tests/e2e/)
python -m pytest tests/ -v --cov            # with coverage report
python -m pytest tests/test_builders.py -v  # single file
python -m pytest tests/e2e/ -v              # browser E2E tests (needs requirements-e2e.txt + chromium)
```

The unit/integration suite uses an in-memory SQLite database — no `.env` or data ingest needed. The browser E2E suite under `tests/e2e/` is excluded from the default `pytest tests/` run via `pytest.ini` (`norecursedirs`) and boots an isolated `main.py` server against a temporary Alembic-migrated SQLite database.
