# DonjonDocs

**A home for your tabletop characters, and your monsters too.**

DonjonDocs is a self-hosted web app that holds your D&D 5e, Level Up: Advanced 5e, Shadowdark, Ultramodern5, and Voidrunner characters in one tidy place. Run it for your group, sign your friends in, and put the paper sheets and scattered spreadsheets away.

## What it is

A *living* digital character sheet. Update an ability score and your skills, saves, AC, attack bonuses, spell DCs and initiative recalculate in front of you. Click a checkbox and a spell slot is spent. Take a short rest and the right things refresh.

Beyond the sheet, every character has tabs for **Allies & Stat Blocks** (your pets, companions, wildshape forms, NPC contacts) and **Notes** (session logs, plot hooks, backstory). Both panes accept Markdown, and you can toggle a switch on the character sheet to redraw them in the typography of an open Player's Handbook: parchment, serif body, small-caps headings.

A **Creature Catalog** sits next to your characters: your private bestiary, with one-click sharing for the rest of your group.

## What it's not

It's not a character builder, validator, or generator. It won't walk you through making a character. It's a place to *store and organise* the characters you've already designed, usually a step or two nicer than paper, with quick cut-and-paste from PDFs and other sites.

## Highlights

**Character sheets that do the math for you.**
- Five rule systems supported first-class, each with its own layout:
  - **D&D 5e** — the classic 2014 core ruleset (Fatigue is renamed back to Exhaustion).
  - **Level Up: Advanced 5e** — deeper, tactical 5e; shows the Strife track and combat maneuvers.
  - **Shadowdark RPG** — old-school and minimalist; hides proficiency bonus.
  - **Ultramodern5** — sci-fi/modern expansion of 5e (see below).
  - **Voidrunner** — sci-fi expansion of Level Up: A5e (see below).
- **Ultramodern5** (sci-fi/modern 5e): its own modern classes and dollar-priced gear, an **optional 7th "Vigor" attribute** you can opt into per character (auto-enabled by the Magus class), and the Vigor-powered **DARK** magic system — a "dark" resource pool with vessel/river/Vigor-Regeneration tracking and a spend +/- on the sheet.
- **Voidrunner** (sci-fi expansion of Level Up: A5e): psionic classes (Psion, Psyknight, Scientist, Scout, Trooper), credits instead of coin, and futuristic weapons, armor, gear, cyberware, and vehicles. It runs on the A5e chassis, so Strife and combat maneuvers come along for free. Psionic powers use a dedicated **"Psionics"** magic type — a spend-from-a-pool that rewords the sheet's spell vocabulary to "Powers".
- Multiclass-aware. Ability scores propagate to skills, saves, attacks, AC and spell DCs.
- HP +/- buttons, exhaustion / strife tracks, death-save counters, equipped armor automatically replaces your AC base.
- Short and long rest mechanics that reset trackers and refill slots.
- Per-item edit pen on Equipment so you can tweak a weapon's properties without deleting and re-adding.

**Allies, pets, and wildshape forms.**
- Each character has an Allies & Stat Blocks tab. Markdown bodies, sorted and edited one at a time.
- Add an ally of type Pet, Companion, or Wildshape and the body field auto-fills with a homebrewery-flavoured stat block template so you can fill in the blanks.
- A **Vehicle** ally type seeds a vehicle/mech stat-block template (AC, HP, speed modes, crew, armament) — handy for a Voidrunner starfighter, a Robotech-style mech, or a fantasy airship. Available for every system except Shadowdark.

**Notes that survive the campaign.**
- Markdown notes for session logs, backstory, plot hooks, faction info, whatever your DM keeps prompting you to write down.

**Creature Catalog**
- Build your own bestiary alongside your characters. Each entry is a homebrewery-style stat block in Markdown, rendered to look like a page from a 5e monster manual. New entries seed from a **Monster** or **Vehicle** template.
- Keep your work private, or flip the **Public** toggle to share with everyone signed in to your instance, handy for the DM who wants to drop polished stat blocks in front of the party, or a player keeping a binder of hirelings and recurring villains.
- Copy a public creature into your own catalog with one click. The copy lands private and yours to remix.
- Paste a stat block in, click **Update from stat block** and the parser fills in size / type / challenge rating for you. (Tested against 121 real homebrewery monsters; works on bullet-list and italic field formats, plural "swarm of *aberrations*" types, and slash-separated compound types like *aberration/undead*.)
- Search and filter by name, creature type, or size. Toggle one-column or two-column page layout per creature.
- Single-creature export and import as JSON, so you can share one monster file with a friend without uprooting your whole catalog.

**It looks like a book.**
- Toggle the **PHB style** switch on a character sheet and your Allies and Notes panes redraw with parchment, BookSanity body text, and small-caps headings.
- The Creature Catalog uses the same typography by default, with an optional two-column page layout for longer stat blocks.

**Yours to host.**
- Whole-instance backup and restore CLI for the DM running the server.
- Role-based accounts: admin / premium / standard. Self-service registration on by default; turn it off with one environment variable.
- Character and creature data lives in a single SQLite file by default. Your group, your data, no third-party signup, no analytics to delete later.

## Run it for your group

You only need Python 3.11+ and Git. The DM (or whoever is hosting) runs steps 1-4 once; players just need a username and password to sign in afterwards.

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

Open **http://localhost:8080** and log in with the admin credentials you just created. To let your players in, hand them the URL (or your machine's IP and port) and either let them self-register, or create their accounts from the Admin > User Management page.

## Managing your group

### Through the web UI

Log in as an admin and head to **Admin > User Management** (or `/admin/users` directly). From there you can:

- **Create users:** click "Create User", fill in username, email, password, and choose a role (admin / premium / standard)
- **Edit users:** change username, email, role, or toggle active/inactive
- **Reset passwords:** set a new password for any user
- **Deactivate users:** soft-delete that you can reverse later by editing the user back to active

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
| **premium** | Create, edit, and manage own characters (unlimited) |
| **standard** | Create, edit, and manage own characters (up to 25) |

### Self-registration

Public registration is enabled by default. Users who register through `/register` get the `standard` role. To disable, set `ALLOW_REGISTRATION=false` in `.env`.

## Backups

Snapshot user-owned data (users, characters, custom globals) to a portable JSON file:

```bash
python cli.py backup                                                  # writes to ./backups/donjondocs-<UTC>.json
python cli.py restore --input <file> --dry-run                        # validate without writing
python cli.py restore --input <file>                                  # merge (default)
python cli.py restore --input <file> --mode replace --yes             # destructive: wipes user data first
```

Backup files contain hashed passwords, treat them as secrets. See [`docs/operations.md`](docs/operations.md) for the file format, merge vs replace semantics, and the production rehearsal procedure.

## For developers

Open source under the GNU AGPL-3.0 (see License below). Contributions welcome, bug reports and pull requests both. Built with FastAPI, NiceGUI, and async SQLAlchemy; no frontend build step.

Detailed docs live in the [`docs/`](docs/) directory:

| Document | Contents |
|----------|----------|
| [Architecture](docs/architecture.md) | Stack, layer diagram, request lifecycle, character-sheet rendering, Creature Catalog |
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
- Ultramodern5 content is provided under the terms of its respective open gaming license.
- Voidrunner content is provided under the terms of its respective open gaming license.
