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
