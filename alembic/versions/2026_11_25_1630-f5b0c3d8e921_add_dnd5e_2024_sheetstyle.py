"""add DND5E_2024 to the sheetstyle enum

Revision ID: f5b0c3d8e921
Revises: e4a9b2c7d810
Create Date: 2026-11-25 16:30:00.000000

Adds the ``DND5E_2024`` member to the ``sheetstyle`` Postgres enum so
`characters.style` can store Dungeons & Dragons 5e (2024 / SRD 5.2) sheets
alongside classic 2014 sheets (`DND5E`; see `app/rule_systems.py::SheetStyle`).

Two dialect notes:
- Postgres: ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block,
  so it must go in an ``autocommit_block()``. ``IF NOT EXISTS`` makes it
  idempotent.
- SQLite (dev/tests): the Enum is a VARCHAR+CHECK that `Base.metadata.create_all`
  rebuilds from the current Python enum, so there is nothing to alter — no-op.

Downgrade is a no-op: Postgres cannot drop an enum value without recreating the
type, and no data or schema depends on DND5E_2024 being absent.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f5b0c3d8e921'
down_revision: Union[str, None] = 'e4a9b2c7d810'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite (and any non-Postgres) rebuilds the Enum CHECK from the Python
        # enum via create_all; nothing to migrate.
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE sheetstyle ADD VALUE IF NOT EXISTS 'DND5E_2024'")


def downgrade() -> None:
    # Postgres cannot drop an enum value in place; nothing depends on its absence.
    pass
