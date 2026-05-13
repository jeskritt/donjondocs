"""
AI Helper Docstring
Purpose: Pydantic validation tests for the Creature catalog schemas — defaults, bounds (columns must be 1 or 2), and round-trip through model_dump/model_validate.
Interactions:
- Targets `app.schemas.creature.{Creature, CreatureCreate, CreatureUpdate}`.
"""

import pytest
from pydantic import ValidationError

from app.schemas.creature import Creature, CreatureCreate, CreatureUpdate


def test_creature_create_defaults():
    """Defaults: empty metadata, habitat 'Any', is_public False, columns 1."""
    c = CreatureCreate(name="Test")
    assert c.name == "Test"
    assert c.body_md == ""
    assert c.creature_type == ""
    assert c.size == ""
    assert c.challenge_rating == ""
    assert c.habitat == "Any"
    assert c.is_public is False
    assert c.columns == 1


def test_creature_create_requires_name():
    with pytest.raises(ValidationError):
        CreatureCreate(name="")


def test_columns_must_be_one_or_two():
    """The schema clamps `columns` to 1 or 2 — the UI ships a toggle, not a
    free-int input, but the schema is the enforcement point."""
    with pytest.raises(ValidationError):
        CreatureCreate(name="X", columns=3)
    with pytest.raises(ValidationError):
        CreatureCreate(name="X", columns=0)
    # 1 and 2 both pass.
    CreatureCreate(name="X", columns=1)
    CreatureCreate(name="X", columns=2)


def test_update_all_fields_optional():
    """CreatureUpdate accepts partial patches — model_dump(exclude_unset=True)
    is what the service uses to apply only the fields the client sent."""
    patch = CreatureUpdate(name="Renamed")
    diff = patch.model_dump(exclude_unset=True)
    assert diff == {"name": "Renamed"}


def test_round_trip_through_model_dump():
    payload = CreatureCreate(
        name="Test",
        body_md="...",
        creature_type="Beast",
        size="Medium",
        challenge_rating="1/4",
        habitat="Forest",
        is_public=True,
        columns=2,
    )
    reborn = CreatureCreate.model_validate(payload.model_dump())
    assert reborn == payload
