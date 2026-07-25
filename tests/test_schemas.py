"""
AI Helper Docstring
Purpose: Pydantic baseline validations proving exact validation constraint exceptions natively throw when given incorrect inputs (like bad enums).
Interactions:
- Focuses tests mainly on `app.schemas.*` behaviors.
"""

import pytest
from pydantic import ValidationError

from app.schemas.char_sheet_global import (
    SheetStyle,
    Class,
    Weapon,
    MagicType,
)

def test_sheet_style_enum():
    assert SheetStyle.DND5E == "Dungeons & Dragons 5e"
    assert SheetStyle.SHADOWDARK == "Shadowdark RPG"

def test_class_model_validates_correctly():
    # Valid class data
    class_data = {
        "name": "Fighter",
        "hit_dice": "d10",
        "primary_ability": "Strength",
        "saving_throws": "Strength, Constitution",
        "proficiencies": "All",
        "source": SheetStyle.DND5E,
        "owner_id": None
    }
    obj = Class(**class_data)
    assert obj.name == "Fighter"
    assert obj.source == SheetStyle.DND5E

def test_class_model_fails_on_invalid_source():
    # Invalid source enum
    class_data = {
        "name": "Fighter",
        "hit_dice": "d10",
        "primary_ability": "Strength",
        "saving_throws": "Strength, Constitution",
        "proficiencies": "All",
        "source": "Invalid Game Setup",
        "owner_id": None
    }
    with pytest.raises(ValidationError):
        Class(**class_data)

def test_weapon_model_handles_notes():
    weapon_data = {
        "name": "Longsword",
        "source": SheetStyle.SHADOWDARK,
        "notes": "Versatile, Heavy"
    }
    w = Weapon(**weapon_data)
    assert w.notes == "Versatile, Heavy"


def test_inventory_item_is_custom_defaults_false_and_round_trips():
    """Library snapshots stay is_custom=False; the flag round-trips through model_dump."""
    from app.schemas.char_sheet_specific import InventoryItem

    pristine = InventoryItem(item_type="item", name="Torch", quantity=10)
    assert pristine.is_custom is False

    dumped = pristine.model_dump()
    assert dumped["is_custom"] is False
    assert InventoryItem.model_validate(dumped).is_custom is False

    customised = InventoryItem(item_type="item", name="Star Charm", is_custom=True)
    assert InventoryItem.model_validate(customised.model_dump()).is_custom is True

    # Older inventory JSON without the field should still load cleanly.
    legacy = {"item_type": "item", "name": "Bedroll", "quantity": 1}
    assert InventoryItem.model_validate(legacy).is_custom is False


def test_character_attunement_bonus_defaults_zero_and_round_trips():
    """The attunement-limit bonus defaults to 0 and survives dump/reload; legacy
    character JSON without the field loads at the default."""
    from app.schemas.char_sheet_specific import (
        Character, Race, CharacterStat, CharacterProficiency,
    )

    base = dict(
        owner_id="u1", style=SheetStyle.DND5E, name="Hero",
        race=Race(ancestry="Human", culture=None, lineage=None),
        background="Sage", prof_bonus=2,
        ac=CharacterStat(base=10, misc=0),
        initiative=CharacterStat(base=0, misc=0),
        inspiration=False, conditions=[], speed=30, size="Medium",
        proficiency=CharacterProficiency(
            weapon=[], armor=[], language=[], instrument=[], tool=[], game=[]
        ),
    )

    default_char = Character(**base)
    assert default_char.attunement_bonus == 0
    assert Character.model_validate(default_char.model_dump()).attunement_bonus == 0

    raised = Character(**base, attunement_bonus=2)
    assert Character.model_validate(raised.model_dump()).attunement_bonus == 2

    legacy = default_char.model_dump()
    legacy.pop("attunement_bonus")
    assert Character.model_validate(legacy).attunement_bonus == 0
