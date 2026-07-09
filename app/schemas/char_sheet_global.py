"""
AI Helper Docstring
Purpose: Pydantic abstractions dictating Global Rule system models and enums.
Interactions:
- Referenced heavily by `char_sheet_specific.py` and `ingest.py`.
"""

"""
This the schema for the character sheets that are accessible to all users. The
building blocks of the character sheets are defined here. This is not a complete
character sheet, but rather a collection of fields that can be used to create
character sheets.

The goal is to provide a framework for generic 5e character sheets, with the
ability to add custom fields and options for different styles of character sheets,
and for different 5e game systems

Each  model in this module should have a reference entry. This allows filtering
so only the right entries are used to build a specific style of character sheet

If a model has a source field, that should be where it comes from. for example
Ability can come from class, archetype, heritage, culture, background, feat, or
just a freebie from the DM. 
"""

import enum
from pydantic import BaseModel, Field

# Re-exported from app.rule_systems so existing
# `from app.schemas.char_sheet_global import SheetStyle` imports keep working.
from app.rule_systems import SheetStyle  # noqa: F401


# Canonical 5e-flavoured creature taxonomies. Plain tuples (not enums) so the
# DB column can store a comma-joined free-text value while the UI and parser
# validate against this list. Used by the Creature Catalog.
CREATURE_TYPES: tuple[str, ...] = (
    "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental",
    "Fey", "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead",
    # Vehicles/mechs/starships live as stat blocks too (Voidrunner, UM5, airships);
    # kept in the taxonomy so the parser and catalog filter recognise them.
    "Vehicle",
)
CREATURE_SIZES: tuple[str, ...] = (
    "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan", "Titanic",
)


class MagicType(str, enum.Enum):
    """
    The type of magic system used by the character.

    SLOTS: warlock style
    PERLEVEL: Typical caster (ie. wizard/sorcerer) style
    POINTS: spell points style
    SHADOWDARK: Shadowdark RPG style
    DARK: Ultramodern5 "dark" pool — Vigor-powered spend-to-cast (like POINTS,
          but with vessel/river/VR presentation)
    PSIONICS: Voidrunner psionic powers — mechanically identical to POINTS (a
          single spend-from-a-pool), but surfaced as an obvious "Psionics" choice
          and reworded to "Powers" on the sheet so psi-only characters aren't
          hunting through fantasy-magic options.
    """
    SLOTS = "Slots"
    PERLEVEL = "Slots / Level"
    POINTS = "Spell Points"
    SHADOWDARK = "Shadowdark"
    DARK = "Dark"
    PSIONICS = "Psionics"
    

class SimpleAbility(BaseModel):
    """A single mechanical sub-feature that hangs off an `Ability`.

    The `Ability` / `SimpleAbility` split is intentional and load-bearing —
    do not collapse them. A Feat that grants several small effects models
    as one parent `Ability` with multiple `SimpleAbility` children. Each
    child carries its own description and (planned) stat-adjustment payload,
    which is why the wrapper exists even when an Ability has only one
    sub-feature.

    Future expansion: `SimpleAbility` will gain a structured stat-adjustment
    field (e.g. `+1 to AC` or `proficiency in Perception`) so the engine
    can apply derived effects without parsing prose. The two-level shape
    is what makes that addition possible without a schema rewrite.
    """
    name: str
    description: str
    effect: str | None = None
    source: SheetStyle
    owner_id: str | None = None

class Ability(BaseModel):
    """A top-level rules-catalog entry: a Feat, class feature, racial trait, etc.

    Pairs with `SimpleAbility` (above). The `Ability` is the named container
    a player picks ("Great Weapon Master", "Channel Divinity", …); each
    `SimpleAbility` referenced via `features` is one of the discrete
    mechanical effects that container delivers.

    Catalog-side only: instances on a character sheet are
    `CharacterAbilityEntry` (with `SubAbilityEntry` children) in
    char_sheet_specific.py — the same parent/child shape, materialised
    per character.
    """
    name: str
    description: str | None = None
    source: SheetStyle
    reference: str | None = None
    features: list[str] | None = None # list of FK to SimpleAbility
    owner_id: str | None = None

class Class(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    hit_dice: str
    primary_ability: str
    saving_throws: str
    proficiencies: str
    source: SheetStyle
    owner_id: str | None = None

class Attribute(BaseModel):
    name: str
    alias: str
    description: str | None = None
    reference: str | None = None
    source: SheetStyle | None = None
    owner_id: str | None = None


class Skill(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    attribute: str | None = None # FK to Attribute
    source: SheetStyle | None = None
    owner_id: str | None = None


class Item(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    type: str | None = None
    weight: str | None = None
    value: str | None = None
    effects: str | None = None
    is_container: bool = Field(default=False)
    is_equipable: bool = Field(default=False)
    is_consumable: bool = Field(default=False)
    is_attunable: bool = Field(default=False)
    source: SheetStyle
    owner_id: str | None = None

class Weapon(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    type: str | None = None
    damage: str | None = None
    damage_type: str | None = None
    range: str | None = None
    weight: str | None = None
    value: str | None = None
    notes: str | None = None
    effects: str | None = None
    source: SheetStyle
    owner_id: str | None = None

class Armor(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    type: str | None = None
    armor_class: str | None = None
    strength_requirement: str | None = None
    disadvantage_on_stealth: bool | str | None = None
    weight: str | None = None
    value: str | None = None
    notes: str | None = None
    effects: str | None = None
    source: SheetStyle
    owner_id: str | None = None

class CombatManeuver(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    tradition: str | None = None
    exertion: str | None = None
    activation: str | None = None
    tier: str | None = None
    source: SheetStyle
    owner_id: str | None = None

class Spell(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    level: str | None = None
    school: str | None = None
    classes: str | None = None
    casting_time: str | None = None
    range: str | None = None
    components: str | None = None
    duration: str | None = None
    ritual: bool = Field(default=False)
    concentration: bool = Field(default=False)
    source: SheetStyle
    owner_id: str | None = None

class Destiny(BaseModel):
    name: str
    description: str | None = None
    reference: str | None = None
    src_inspiration: str | None = None # FK to SimpleAbility
    inspiration_feat: str | None = None # FK to SimpleAbility
    fullfillment: str | None = None # FK to SimpleAbility
    source: SheetStyle
    owner_id: str | None = None


class CustomWeaponInput(BaseModel):
    name: str
    weapon_type: str = ""
    damage: str = ""
    damage_type: str = ""
    weapon_range: str = ""
    weight: str = ""
    value: str = ""
    notes: str = ""


class CustomArmorInput(BaseModel):
    name: str
    armor_type: str = ""
    armor_class: str = ""
    strength_requirement: str = ""
    weight: str = ""
    value: str = ""
    notes: str = ""


class CustomItemInput(BaseModel):
    name: str
    item_type: str = ""
    weight: str = ""
    value: str = ""
    effects: str = ""
