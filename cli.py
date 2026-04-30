"""
AI Helper Docstring
Purpose: Command Line Interface for DonjonDocs. Handles execution of administrative scripts (create user, reset password, full-DB user-data backup/restore) via argparse.
Interactions:
- `app.models.*` & `app.schemas.*`: Uses definitions to pipe user inputs into data structures.
- `app.database`, `app.services.user_service`: Triggers the core database transactions to physically mutate user data.
- `app.services.backup_service`: drives the `backup` and `restore` subcommands; produces and consumes the versioned JSON envelope.
"""

"""DonjonDocs CLI — User management and DB backup/restore from the command line.

Usage:
    python cli.py create-user --username admin --email admin@example.com --password "Pass123!" --role admin
    python cli.py list-users
    python cli.py reset-password --email admin@example.com --new-password "NewPass456!"
    python cli.py backup [--output backups/donjondocs-<UTC>.json]
    python cli.py restore --input <file> [--mode {merge,replace}] [--dry-run] [--force] [--yes]
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.database import async_session_factory, engine, Base
from app.models import User, UserRole  # noqa: F401
from app.schemas.user import UserCreate
from app.services.backup_service import (
    BackupEnvelope,
    BackupServiceError,
    RestoreMode,
    create_backup,
    restore_backup,
)
from app.services.user_service import (
    UserServiceError,
    create_user,
    get_user_by_email,
    list_users,
    reset_password,
)


async def _ensure_tables():
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _create_user(args):
    """Create a new user."""
    await _ensure_tables()

    data = UserCreate(
        username=args.username,
        email=args.email,
        password=args.password,
        role=UserRole(args.role),
    )

    async with async_session_factory() as session:
        try:
            user = await create_user(session, data)
            await session.commit()
            print(f"[OK] User created successfully:")
            print(f"  ID:       {user.id}")
            print(f"  Username: {user.username}")
            print(f"  Email:    {user.email}")
            print(f"  Role:     {user.role.value}")
        except UserServiceError as e:
            print(f"[ERROR] {e.message}", file=sys.stderr)
            sys.exit(1)


async def _list_users(args):
    """List all users."""
    await _ensure_tables()

    async with async_session_factory() as session:
        users, total = await list_users(session, limit=100)
        if not users:
            print("No users found.")
            return

        print(f"{'ID':<38} {'Username':<20} {'Email':<30} {'Role':<10} {'Active':<8}")
        print("-" * 110)
        for u in users:
            print(
                f"{u.id:<38} {u.username:<20} {u.email:<30} "
                f"{u.role.value:<10} {'Yes' if u.is_active else 'No':<8}"
            )
        print(f"\nTotal: {total} user(s)")


async def _reset_password(args):
    """Reset a user's password."""
    await _ensure_tables()

    async with async_session_factory() as session:
        try:
            user = await get_user_by_email(session, args.email)
            await reset_password(session, user.id, args.new_password)
            await session.commit()
            print(f"[OK] Password reset for {user.username} ({user.email})")
        except UserServiceError as e:
            print(f"[ERROR] {e.message}", file=sys.stderr)
            sys.exit(1)


def _default_backup_path() -> Path:
    """./backups/donjondocs-YYYYMMDDTHHMMSSZ.json — UTC, sortable, filename-safe."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("backups") / f"donjondocs-{stamp}.json"


async def _backup(args):
    """Snapshot user-owned rows to a JSON envelope on disk."""
    await _ensure_tables()

    output = Path(args.output) if args.output else _default_backup_path()
    output.parent.mkdir(parents=True, exist_ok=True)

    async with async_session_factory() as session:
        try:
            envelope = await create_backup(session)
        except BackupServiceError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    output.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")
    custom_globals = sum(len(v) for v in envelope.user_globals.values())
    addons = sum(len(v) for v in envelope.character_addons.values())
    print(
        f"[OK] wrote {output} "
        f"({len(envelope.users)} users, {len(envelope.characters)} characters, "
        f"{custom_globals} custom globals, {addons} character addons)"
    )
    print("[WARN] Backup contains hashed passwords. Treat the file as a secret.")


async def _restore(args):
    """Restore from a JSON envelope, in merge or replace mode."""
    await _ensure_tables()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        envelope = BackupEnvelope.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] Could not parse backup file: {e}", file=sys.stderr)
        sys.exit(1)

    mode = RestoreMode(args.mode)
    if mode == RestoreMode.REPLACE and not args.dry_run and not args.yes:
        confirm = input(
            "REPLACE mode wipes all users, characters, and custom global rows. "
            "Type 'yes' to continue: "
        ).strip().lower()
        if confirm != "yes":
            print("[ERROR] Aborted.", file=sys.stderr)
            sys.exit(1)

    async with async_session_factory() as session:
        try:
            report = await restore_backup(
                session, envelope,
                mode=mode, dry_run=args.dry_run, force=args.force,
            )
        except BackupServiceError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    prefix = "[DRY-RUN]" if args.dry_run else "[OK]"
    print(
        f"{prefix} mode={report.mode.value} "
        f"users(+{report.users_inserted}/~{report.users_updated}) "
        f"characters(+{report.characters_inserted}/~{report.characters_updated}) "
        f"user_globals(+{report.user_globals_inserted}/~{report.user_globals_updated}) "
        f"addons(+{report.character_addons_inserted}/~{report.character_addons_updated})"
    )


def main():
    """CLI entry point."""
    # Ensure settings are loadable
    try:
        get_settings()
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}", file=sys.stderr)
        print("  Make sure you have a .env file with SECRET_KEY set.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="DonjonDocs CLI — User Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create-user
    create_parser = subparsers.add_parser("create-user", help="Create a new user")
    create_parser.add_argument("--username", required=True, help="Username")
    create_parser.add_argument("--email", required=True, help="Email address")
    create_parser.add_argument("--password", required=True, help="Password (min 8 chars)")
    create_parser.add_argument(
        "--role",
        choices=["admin", "standard", "premium"],
        default="standard",
        help="User role (default: standard)",
    )

    # list-users
    subparsers.add_parser("list-users", help="List all users")

    # reset-password
    reset_parser = subparsers.add_parser("reset-password", help="Reset a user's password")
    reset_parser.add_argument("--email", required=True, help="User's email address")
    reset_parser.add_argument("--new-password", required=True, help="New password (min 8 chars)")

    # backup
    backup_parser = subparsers.add_parser(
        "backup",
        help="Snapshot user-owned rows (users, characters, custom globals) to a JSON file",
    )
    backup_parser.add_argument(
        "--output",
        default=None,
        help="Output file path. Default: ./backups/donjondocs-<UTC-timestamp>.json",
    )

    # restore
    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore user-owned rows from a backup JSON file",
    )
    restore_parser.add_argument("--input", required=True, help="Backup JSON file to restore from")
    restore_parser.add_argument(
        "--mode",
        choices=[m.value for m in RestoreMode],
        default=RestoreMode.MERGE.value,
        help="merge: upsert by primary key (default). replace: wipe matching tables first.",
    )
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count changes, then roll back without writing.",
    )
    restore_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the alembic revision compatibility check.",
    )
    restore_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation for --mode replace.",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    command_map = {
        "create-user": _create_user,
        "list-users": _list_users,
        "reset-password": _reset_password,
        "backup": _backup,
        "restore": _restore,
    }

    asyncio.run(command_map[args.command](args))


if __name__ == "__main__":
    main()
