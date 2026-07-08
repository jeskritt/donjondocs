"""
AI Helper Docstring
Purpose: Concrete Builder for Ultramodern5 (UM5) — a sci-fi/modern *expansion* of
D&D 5e that shares the core 5e math. UM5 therefore inherits the vanilla-5e view
model wholesale (no Destiny, "Exhaustion" wording, no combat maneuvers) and adds
only UM5-specific concerns as the feature set grows.
Interactions:
- `app.builders.dnd5e.py`: Inherits `DnD2014Builder` — the closest 5e baseline.
- `app.builders.__init__.get_builder`: dispatches `SheetStyle.UM5` here.

This subclass is deliberately thin today (UM5 Phase 1 is content-only: its own
classes, modern gear, and skills seeded under `source="Ultramodern 5e"`). It is
the extension point for the optional Vigor attribute (Phase 2) and the DARK magic
system (Phase 3); those will override the relevant `build_*` methods here rather
than branching on style at the UI layer.
"""

from app.builders.dnd5e import DnD2014Builder


class Um5Builder(DnD2014Builder):
    """Ultramodern5 sheet builder. Inherits the D&D 2014 view model unchanged."""
    pass
