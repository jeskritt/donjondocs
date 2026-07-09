"""add VOIDRUNNER to the sheetstyle enum

Revision ID: b7f3c1a9d240
Revises: c99b0e85e40f
Create Date: 2026-07-09 09:00:00.000000

Adds the ``VOIDRUNNER`` member to the ``sheetstyle`` Postgres enum so
`characters.style` can store Voidrunner sheets. Voidrunner is a sci-fi expansion
of Level Up: Advanced 5e (see `app/rule_systems.py::SheetStyle`).

This is the repo's first enum-value migration — UM5/GENEFUNK/CARBON shipped in the
baseline. Two dialect notes:
- Postgres: ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block, so
  it must go in an ``autocommit_block()``. ``IF NOT EXISTS`` makes it idempotent.
- SQLite (dev/tests): the Enum is a VARCHAR+CHECK that `Base.metadata.create_all`
  rebuilds from the current Python enum, so there is nothing to alter — no-op.

Downgrade is a no-op: Postgres cannot drop an enum value without recreating the
type, and no data or schema depends on VOIDRUNNER being absent.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7f3c1a9d240'
down_revision: Union[str, None] = 'c99b0e85e40f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite (and any non-Postgres) rebuilds the Enum CHECK from the Python
        # enum via create_all; nothing to migrate.
        return
    # ADD VALUE cannot run in a transaction — use an autocommit block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE sheetstyle ADD VALUE IF NOT EXISTS 'VOIDRUNNER'")


def downgrade() -> None:
    # Postgres cannot drop an enum value in place; nothing depends on its absence.
    pass
