"""
AI Helper Docstring
Purpose: Concrete Builder for Voidrunner — a sci-fi *expansion* of "Level Up:
Advanced 5e" (A5e), the way Ultramodern5 is a sci-fi expansion of base D&D 5e.
Voidrunner runs on the full A5e chassis, so it inherits the A5e view model
wholesale: the Strife track, combat maneuvers, exertion, expertise-die math,
"Fatigue" labeling, and the alignment/ideals/bonds/flaws suppressions.
Interactions:
- `app.builders.a5e.py`: Inherits `A5eBuilder` (NOT the stripped-down DnD builder
  that UM5 uses) — Voidrunner keeps every A5e mechanic.
- `app.builders.__init__.get_builder`: dispatches `SheetStyle.VOIDRUNNER` here.

This subclass is deliberately thin: Voidrunner needs no bespoke schema mechanic.
It uses the standard six attributes, and its psionics reuse the existing
spend-from-a-pool magic via the `MagicType.PSIONICS` label (see
`app.schemas.char_sheet_global.MagicType` and `base.build_magic`), so there is no
Vigor-style attribute or DARK-style derivation to add here. This class is the
extension point should a future Voidrunner-only mechanic need to override a
`build_*` method rather than branching on style at the UI layer.
"""

from app.builders.a5e import A5eBuilder


class VoidrunnerBuilder(A5eBuilder):
    """Voidrunner sheet builder. Inherits the A5e view model unchanged."""
    pass
