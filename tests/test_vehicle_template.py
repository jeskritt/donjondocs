"""
AI Helper Docstring
Purpose: Guard the cross-system Vehicle/Mech stat-block template — that it exists,
that the tolerant `parse_stat_block` extracts name/size/type from it (so "Update
from stat block" works on vehicles), that "Vehicle" is a recognised creature type,
and that the Allies per-type template map resolves Vehicle → the vehicle template
while Pet/Companion/Wildshape keep the monster template and non-seedable types
return None.
Interactions:
- `app.services.creature_parser.parse_stat_block`
- `app.schemas.char_sheet_global.CREATURE_TYPES`
- `app.ui.components.sheet.allies.{TYPE_TEMPLATES, _read_stat_block_template}`
"""

from pathlib import Path

from app.services.creature_parser import parse_stat_block
from app.schemas.char_sheet_global import CREATURE_TYPES
from app.ui.components.sheet.allies import TYPE_TEMPLATES, _read_stat_block_template

_SHEET_DIR = Path(__file__).resolve().parent.parent / "app" / "ui" / "components" / "sheet"
_VEHICLE_TPL = _SHEET_DIR / "vehicle_stat_block_template.md"
_MONSTER_TPL = _SHEET_DIR / "stat_block_template.md"


def test_template_files_exist():
    assert _VEHICLE_TPL.is_file()
    assert _MONSTER_TPL.is_file()


def test_vehicle_type_is_recognised():
    assert "Vehicle" in CREATURE_TYPES


def test_vehicle_template_parses():
    """The vehicle template follows the `> ## Name` / `> *Size, Type*` conventions,
    so the metadata parser lifts name/size/type for free (no Challenge line)."""
    parsed = parse_stat_block(_VEHICLE_TPL.read_text(encoding="utf-8"))
    assert parsed.get("name")                     # a heading name was found
    assert parsed.get("size") in {"Gargantuan", "Huge", "Large"}
    assert parsed.get("creature_type") == "Vehicle"
    assert "challenge_rating" not in parsed       # vehicles carry no CR


def test_ally_type_template_map():
    # Vehicle resolves to its own template; the animal types share the monster one.
    assert TYPE_TEMPLATES["Vehicle"] == "vehicle_stat_block_template.md"
    for t in ("Pet", "Companion", "Wildshape"):
        assert TYPE_TEMPLATES[t] == "stat_block_template.md"


def test_read_stat_block_template_by_type():
    vehicle = _read_stat_block_template("Vehicle")
    monster = _read_stat_block_template("Pet")
    assert vehicle == _VEHICLE_TPL.read_text(encoding="utf-8")
    assert monster == _MONSTER_TPL.read_text(encoding="utf-8")
    assert vehicle != monster
    # Non-seedable / unknown types don't seed anything.
    assert _read_stat_block_template("Contact") is None
    assert _read_stat_block_template("") is None
