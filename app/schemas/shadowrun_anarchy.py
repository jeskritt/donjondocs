"""
AI Helper Docstring
Purpose: Pydantic v2 schema for Shadowrun: Anarchy 2.0 character sheets (`AnarchyCharacter`) and its flat, composable sub-models (skills, specializations, Shadow Amps with Markdown templates, weapons, spells, armor, equipment, wound monitor). Also defines metatype limits and canonical skill metadata constants.
Interactions:
- `app.schemas.registry.parse_character`: dispatches `SheetStyle.SHADOWRUN_ANARCHY_2` blobs here.
- `app.builders.shadowrun_anarchy.ShadowrunAnarchyBuilder`: consumes `AnarchyCharacter` to derive Dice Pools, Risk Reduction, Essence penalties, Wound Thresholds, Weapon DVs, and Nuyen investment totals.
- `app.services.character_seeding`: constructs initial blank `AnarchyCharacter` dicts.
- `app.ui.components.sheet_anarchy.*`: reads/edits these fields through `_save()`.
"""

from __future__ import annotations

import enum
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.rule_systems import SheetStyle


class Metatype(str, enum.Enum):
    """Core Sixth World metatypes in Shadowrun: Anarchy 2.0."""

    HUMAN = "Human"
    ELF = "Elf"
    DWARF = "Dwarf"
    ORK = "Ork"
    TROLL = "Troll"


# Per-metatype attribute maxima, starting Edge, and narrative racial quality.
# Source: Shadowrun: Anarchy 2.0 core attribute table.
METATYPE_RULES: dict[Metatype, dict[str, object]] = {
    Metatype.HUMAN: {
        "caps": {"STR": 4, "AGI": 4, "WIL": 4, "LOG": 4, "CHA": 4},
        "edge_base": 4,
        "racial_quality": "None",
    },
    Metatype.ELF: {
        "caps": {"STR": 4, "AGI": 4, "WIL": 4, "LOG": 4, "CHA": 5},
        "edge_base": 3,
        "racial_quality": "Low-light vision",
    },
    Metatype.DWARF: {
        "caps": {"STR": 4, "AGI": 4, "WIL": 5, "LOG": 4, "CHA": 4},
        "edge_base": 3,
        "racial_quality": "Thermographic vision",
    },
    Metatype.ORK: {
        "caps": {"STR": 5, "AGI": 4, "WIL": 4, "LOG": 4, "CHA": 4},
        "edge_base": 3,
        "racial_quality": "Low-light vision",
    },
    Metatype.TROLL: {
        "caps": {"STR": 6, "AGI": 4, "WIL": 4, "LOG": 4, "CHA": 4},
        "edge_base": 3,
        "racial_quality": "Thermographic vision",
    },
}


class AmpType(str, enum.Enum):
    """The 9 unified Shadow Amp categories."""

    QUALITY = "Quality"
    AWAKENED = "Awakened"
    CYBERWARE = "Cyberware"
    BIOWARE = "Bioware"
    ADEPT_POWER = "Adept Power"
    EQUIPMENT = "Equipment"
    CYBERDECK = "Cyberdeck"
    VEHICLE_DRONE = "Vehicle or Drone"
    CONTACT = "Contact"


# Default Essence cost when adding a new Shadow Amp of a given type.
DEFAULT_AMP_ESSENCE: dict[AmpType, float] = {
    AmpType.CYBERWARE: 1.0,
    AmpType.BIOWARE: 0.5,
}


class AmpEffect(BaseModel):
    """Optional structured mechanical modifier evaluated by the builder.

    Keeps derived sheet math (Risk Reduction, +1 Armor, extra wound boxes,
    unarmed DV bonuses, mental protection) accurate without parsing prose.
    """

    kind: Literal[
        "rr_skill",
        "rr_spec",
        "rr_attr",
        "armor_bonus",
        "light_wound_box",
        "serious_wound_box",
        "unarmed_dv_bonus",
        "mental_protection",
        "narrative",
    ] = "narrative"
    target: str = ""
    value: int = 1
    note: str = ""


class ShadowAmp(BaseModel):
    """A single Shadow Amp owned by the runner.

    `body_md` holds editable Markdown details — for Cyberdecks, Vehicles,
    Drones, and Contacts this is seeded with a stat-block template or prebuilt
    library entry that the player can customize locally.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    amp_type: AmpType = AmpType.EQUIPMENT
    rating: int = Field(default=1, ge=0)
    essence_cost: float = Field(default=0.0, ge=0.0)
    effects: list[AmpEffect] = Field(default_factory=list)
    body_md: str = ""
    is_custom: bool = False


class AnarchySpecialization(BaseModel):
    """A skill specialization granting +2 dice pool (up to 10)."""

    name: str
    attribute: str = "AGI"  # STR | AGI | WIL | LOG | CHA
    bonus: int = 2


class AnarchySkill(BaseModel):
    """One of the 14 active Shadowrun: Anarchy 2.0 skills (rating 0–8)."""

    name: str
    category: str = "General"  # General | Fighting | Technical | Social | Magic
    rating: int = Field(default=0, ge=0, le=8)
    attribute: str = "AGI"  # Default linked attribute
    alt_attributes: list[str] = Field(default_factory=list)
    specializations: list[AnarchySpecialization] = Field(default_factory=list)
    example_uses: str | None = None


class AnarchyWeapon(BaseModel):
    """Weapon entry with fixed or STR-derived DV and four range bands."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    weapon_type: str = "Weapon"  # "Weapon" (2,500¥) | "Spec. weapon" (5,000¥) | "Unarmed"
    dv: str = "STR"  # Fixed int ("5") or formula ("STR", "STR+1", "STR+2")
    range_close: str = "OK"  # "OK" | "Dis." | "—"
    range_short: str = "—"
    range_medium: str = "—"
    range_long: str = "—"
    skill: str = "Ranged Weapons"
    specialization: str = ""
    notes: str = ""
    is_custom: bool = False


class AnarchySpell(BaseModel):
    """Spell entry for Awakened characters (5,000¥ each)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str = "Combat"  # Combat | Detection | Health | Illusion | Manipulation
    subtype: str = ""
    duration: Literal["I", "S"] = "I"  # Instantaneous vs Sustained
    threshold: str = ""
    sustained_active: bool = False
    notes: str = ""
    is_custom: bool = False


class AnarchyArmor(BaseModel):
    """Armor entry (2,500¥ per rating point)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    rating: int = Field(default=1, ge=0)
    slot: Literal["main", "alternate", "inactive"] = "inactive"
    notes: str = ""
    is_custom: bool = False


class AnarchyEquipmentItem(BaseModel):
    """Narrative/mundane gear item (default 2,500¥)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str = "Gear"
    cost: int = Field(default=2500, ge=0)
    notes: str = ""
    is_custom: bool = False


class WoundMonitor(BaseModel):
    """Discrete condition monitor boxes (base 2 Light, 1 Serious, 1 Incap)."""

    light: list[bool] = Field(default_factory=lambda: [False, False])
    serious: list[bool] = Field(default_factory=lambda: [False])
    incapacitated: bool = False
    stim_patch_active: bool = False


class AnarchyCharacter(BaseModel):
    """Source-of-truth schema for a Shadowrun: Anarchy 2.0 runner."""

    name: str
    style: SheetStyle = SheetStyle.SHADOWRUN_ANARCHY_2
    owner_id: str | None = None
    metatype: Metatype = Metatype.HUMAN

    # Core Attributes (human 1–4; metatypes raise one attribute cap to 5 or 6)
    strength: int = Field(default=2, ge=1, le=8)
    agility: int = Field(default=2, ge=1, le=8)
    willpower: int = Field(default=2, ge=1, le=8)
    logic: int = Field(default=2, ge=1, le=8)
    charisma: int = Field(default=2, ge=1, le=8)

    # Edge (resets to edge_base each adventure; unlimited gain during play)
    edge_current: int = Field(default=4, ge=0)
    edge_base: int = Field(default=4, ge=1)

    # Narrative traits (5 Keywords, 4 Dispositions, 4 Cues, Knowledge Skills)
    keywords: list[str] = Field(default_factory=lambda: ["", "", "", "", ""])
    dispositions: list[str] = Field(default_factory=lambda: ["", "", "", ""])
    cues: list[str] = Field(default_factory=lambda: ["", "", "", ""])
    knowledge_skills: list[str] = Field(default_factory=list)

    # Active play & gear
    skills: list[AnarchySkill] = Field(default_factory=list)
    shadow_amps: list[ShadowAmp] = Field(default_factory=list)
    weapons: list[AnarchyWeapon] = Field(default_factory=list)
    spells: list[AnarchySpell] = Field(default_factory=list)
    armor: list[AnarchyArmor] = Field(default_factory=list)
    equipment: list[AnarchyEquipmentItem] = Field(default_factory=list)
    wounds: WoundMonitor = Field(default_factory=WoundMonitor)
    nuyen: int = Field(default=0, ge=0)
    bio: str = ""
