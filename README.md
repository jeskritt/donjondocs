# DonjonDocs

A web app for creating and managing tabletop RPG character sheets. Supports **D&D 5e**, **Level Up: Advanced 5e**, and **Shadowdark RPG**.

Built with FastAPI, NiceGUI, and async SQLAlchemy. Dark-mode UI with reactive server-rendered pages — no frontend build step required.

## Features

- Full character sheets with abilities, skills, equipment, spells, features, and more
- Per-system builders that adapt the sheet layout to each rule system
- Import/export characters as JSON
- Role-based access control (admin, premium, standard)
- Self-service registration and profile management
- Admin dashboard for user management

## Quick Start (local dev)

### Prerequisites

- Python 3.11+
- Git

### 1. Clone and install

```bash
git clone <repo-url>
cd donjondocs
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and set `SECRET_KEY` to a random string:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Everything else has sensible defaults. The SQLite database file (`donjondocs.db`) is created automatically on first run.

### 3. Create your admin account

```bash
python cli.py create-user --username admin --email admin@example.com --password "YourPassword123!" --role admin
```

### 4. Start the app

```bash
python main.py
```

Open **http://localhost:8080** and log in with the admin credentials you just created.

## Managing Users

### Through the web UI

Log in as an admin and navigate to **Admin > User Management** (or go to `/admin/users` directly). From there you can:

- **Create users** — click "Create User", fill in username, email, password, and select a role (admin / premium / standard)
- **Edit users** — change username, email, role, or toggle active/inactive status
- **Reset passwords** — set a new password for any user
- **Deactivate users** — soft-delete that can be reversed by editing the user back to active

### Through the CLI

```bash
python cli.py create-user --username alice --email alice@example.com --password "Pass123!" --role standard
python cli.py list-users
python cli.py reset-password --email alice@example.com --new-password "NewPass123!"
```

### Roles

| Role | Access |
|------|--------|
| **admin** | Full access to all characters and the user management dashboard |
| **premium** | Standard access (reserved for future expansion) |
| **standard** | Create, edit, and manage own characters (up to 25) |

### Self-registration

Public registration is enabled by default. Users who register through `/register` get the `standard` role. To disable registration, set `ALLOW_REGISTRATION=false` in `.env`.

## Backups

Snapshot user-owned data (users, characters, custom globals) to a portable JSON file:

```bash
python cli.py backup                                                  # writes to ./backups/donjondocs-<UTC>.json
python cli.py restore --input <file> --dry-run                        # validate without writing
python cli.py restore --input <file>                                  # merge (default)
python cli.py restore --input <file> --mode replace --yes             # destructive: wipes user data first
```

Backup files contain hashed passwords — treat them as secrets. See [`docs/operations.md`](docs/operations.md) for the file format, merge vs replace semantics, and the production rehearsal procedure.

## Documentation

Detailed docs live in the [`docs/`](docs/) directory:

| Document | Contents |
|----------|----------|
| [Architecture](docs/architecture.md) | Stack, layer diagram, request lifecycle, character-sheet rendering |
| [Database](docs/database.md) | Tables, ER diagram, character data blob structure |
| [Dependencies](docs/dependencies.md) | Module dependency graph |
| [Deployment](docs/deployment.md) | Environment variables, production setup, systemd example |
| [Development](docs/development.md) | CLI reference, running tests, data ingestion, migrations |
| [Operations](docs/operations.md) | Backup & restore CLI, file format, schema-version safety |
| [RBAC](docs/rbac.md) | Roles, auth flow, authorization rules |

## License

This project contains both source code and game data, which are licensed separately.

### Source Code
The source code for DonjonDocs is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the `LICENSE` file for details. 

If you modify this application and offer it as a service over a network, you must make the source code of your modified version available to your users under the same AGPL-3.0 license.

### Game Data
The game mechanics, character class data, items, and rules (located in the CSV files and rendered by the application) are the property of their respective creators and are **NOT** covered by the AGPL-3.0 license.
- D&D 5e content is provided under the terms of the [Wizards of the Coast Systems Reference Document 5.1](https://dnd.wizards.com/resources/systems-reference-document) (licensed under CC-BY-4.0).
- Level Up: Advanced 5e content is provided under the terms of its respective open gaming license.
