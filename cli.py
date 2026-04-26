"""
AI Helper Docstring
Purpose: Command Line Interface for DonjonDocs. Handles execution of administrative scripts (create user, reset password) via argparse.
Interactions: 
- `app.models.*` & `app.schemas.*`: Uses definitions to pipe user inputs into data structures.
- `app.database`, `app.services.user_service`: Triggers the core database transactions to physically mutate user data.
"""

"""DonjonDocs CLI — User management from the command line.

Usage:
    python cli.py create-user --username admin --email admin@example.com --password "Pass123!" --role admin
    python cli.py list-users
    python cli.py reset-password --email admin@example.com --new-password "NewPass456!"
"""

import argparse
import asyncio
import sys

from app.config import get_settings
from app.database import async_session_factory, engine, Base
from app.models import User, UserRole  # noqa: F401
from app.schemas.user import UserCreate
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

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    command_map = {
        "create-user": _create_user,
        "list-users": _list_users,
        "reset-password": _reset_password,
    }

    asyncio.run(command_map[args.command](args))


if __name__ == "__main__":
    main()
