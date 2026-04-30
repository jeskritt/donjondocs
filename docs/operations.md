# Operations

- [Backup & Restore](#backup--restore)
  - [What's in a backup](#whats-in-a-backup)
  - [Backup file format](#backup-file-format)
  - [Creating a backup](#creating-a-backup)
  - [Restoring from a backup](#restoring-from-a-backup)
  - [Schema-version safety](#schema-version-safety)
  - [Production rehearsal](#production-rehearsal)

## Backup & Restore

DonjonDocs ships a CLI for snapshotting and restoring **user-owned data** to a single JSON file. There is no scheduled or cloud-uploaded backup — the file is yours to copy somewhere safe.

> **The backup file contains hashed passwords. Treat it as a secret.** Store it the same way you store `.env` files: encrypted, off the application server, and out of source control.

### What's in a backup

| Included | Excluded |
|---|---|
| All rows of `users` | — |
| All rows of `characters` (with `character_data` migrated to the latest schema) | — |
| All rows of `character_allies` and `character_notes` (per-character relational addons; added in `BACKUP_VERSION` 2) | — |
| Rows of the nine `global_*` tables where `owner_id IS NOT NULL` (custom items, spells, abilities a user has added) | Bulk rule data — rows in `global_*` tables where `owner_id IS NULL`. That data is reproducible from `data/*.csv` via `python -m app.cli.ingest`. |

### Backup file format

```json
{
  "backup_version": 2,
  "exported_at": "2026-04-30T12:34:56+00:00",
  "alembic_revision": "f9f7baa647cc",
  "character_data_version": 6,
  "users":      [ /* User rows */ ],
  "characters": [ /* CharacterRecord rows */ ],
  "user_globals": {
    "global_item":   [ ... ],
    "global_weapon": [ ... ],
    "global_armor":  [ ... ],
    "global_spell":  [ ... ],
    "global_ability":[ ... ],
    "global_class":  [ ... ],
    "global_attribute": [ ... ],
    "global_skill":  [ ... ],
    "global_combat_maneuver": [ ... ],
    "global_destiny":[ ... ]
  },
  "character_addons": {
    "character_allies": [ ... ],
    "character_notes":  [ ... ]
  }
}
```

`backup_version` 1 (without the `character_addons` bucket) is still accepted by the loader — missing addon buckets default to empty, so older artifacts restore cleanly into a v2 codebase.

- `alembic_revision` is read from the source DB's `alembic_version` table. Restore rejects mismatched revisions unless you pass `--force`.
- `character_data_version` is the version of each character's JSON blob (currently 5). Older blobs are migrated up to this version at backup time, so restored characters always match the current `Character` schema (`app/schemas/char_sheet_specific.py`).

### Creating a backup

```bash
# Default: writes to ./backups/donjondocs-<UTC-timestamp>.json
python cli.py backup

# Or specify a path:
python cli.py backup --output /secure/path/donjondocs-prod.json
```

Output:

```
[OK] wrote backups/donjondocs-20260430T123456Z.json (3 users, 7 characters, 2 custom globals)
[WARN] Backup contains hashed passwords. Treat the file as a secret.
```

### Restoring from a backup

Two modes, both atomic:

| Mode | Behavior |
|---|---|
| `merge` *(default)* | Upsert every row by primary key. Existing rows updated, new rows inserted, **rows already in the target that are not in the backup are left alone**. Safe and incremental. |
| `replace` | Wipe `users`, `characters`, and user-owned `global_*` rows, then load the envelope. **Destructive** — requires `--yes` or interactive confirmation. |

Recommended workflow — always start with `--dry-run`:

```bash
# 1. Validate everything and print counts; the DB is not touched.
python cli.py restore --input backups/donjondocs-20260430.json --dry-run

# 2. Once the dry-run looks right, run it for real.
python cli.py restore --input backups/donjondocs-20260430.json
#   ...or, for a full disaster recovery, replace mode (interactive prompt):
python cli.py restore --input backups/donjondocs-20260430.json --mode replace
#   ...or non-interactive, e.g. from a script:
python cli.py restore --input backups/donjondocs-20260430.json --mode replace --yes
```

Output:

```
[OK] mode=merge users(+1/~0) characters(+3/~0) user_globals(+0/~0)
```

`+N` is inserted, `~N` is updated. `[DRY-RUN]` replaces `[OK]` for dry-runs.

### Schema-version safety

Restore checks two compatibility points before touching the DB:

1. **Alembic revision.** The backup's `alembic_revision` must match the target's current head, or `--force` is required.
   - Trying to restore a backup taken at revision `abc123` into a DB at revision `def456` will fail loudly. Run `alembic upgrade head` on the target first, then restore.
2. **`character_data` schema.** Every character is run through the migration chain in `app/services/character_io.py` and validated against the `Character` Pydantic schema **before** any writes. A single bad blob aborts the entire restore — no partial state.

### Production rehearsal

Once a quarter (or after any non-trivial schema change), prove the backup actually restores:

```bash
# 1. Take a fresh backup from prod.
python cli.py backup --output /tmp/prod-rehearsal.json

# 2. Spin up a scratch local Postgres and point a checkout at it.
DATABASE_URL=postgresql+asyncpg://localhost/donjondocs_rehearsal alembic upgrade head
DATABASE_URL=postgresql+asyncpg://localhost/donjondocs_rehearsal \
  python cli.py restore --input /tmp/prod-rehearsal.json --mode replace --yes

# 3. Boot the app against the scratch DB and log in as a known user.
DATABASE_URL=postgresql+asyncpg://localhost/donjondocs_rehearsal python main.py

# 4. Confirm characters render and inline edits save. Tear down the scratch DB.
```

If step 4 fails, your last "good" backup is suspect — investigate before the next outage.
