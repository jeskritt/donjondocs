"""
AI Helper Docstring
Purpose: Pydantic abstractions tracking the dynamic logic states of active User Player Characters (Hit points, equipped status, fatigue, defenses, extra magic resources, physical/identity description).
Interactions:
- Used exclusively by `app.builders.*` to dynamically read an individual character's live data into the UI view layers.
"""

"""
This the schema for the character sheets that are specific to each user. The
building blocks of the character sheets are defined here. This is not a complete
character sheet, but rather a collection of fields that can be used to create
character sheets.
"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator
from app.schemas.char_sheet_global import (MagicType,
                                           SheetStyle,
                                          )


class AbilityScore(BaseModel):
    """
    Breakdown of a single ability score.

    :param base: the base (rolled/point-buy) value
    :param racial: bonus from race/ancestry
    :param level: bonus from level-up ASI
    :param misc: any other bonuses (items, spells, etc.)
    """
    base: int = Field(default=10, ge=3, le=24)
    racial: int = 0
    level: int = 0
    misc: int = 0


class CharacterSavingThrowSimple(BaseModel):
    """
    Inline saving throw record stored in the character JSON blob.

    :param attribute: abbreviated attribute name ("STR", "DEX", etc.)
    :param proficiency: 0=none, 1=half, 2=full, 3=expertise/double
    :param misc: flat misc modifier
    """
    attribute: str
    proficiency: int = Field(default=0, ge=0, le=3)
    misc: int = 0


class CharacterSkillSimple(BaseModel):
    """
    Inline skill record stored in the character JSON blob.

    :param name: the skill name (e.g., "Perception")
    :param attribute: abbreviated attribute ("STR", "WIS", etc.)
    :param proficiency: 0=none, 1=half, 2=full, 3=expertise
    :param misc: flat misc modifier
    :param example_uses: example uses from the rulebook (populated from GlobalSkill at add-time)
    :param notes: user-authored notes (specialties, expertise flavor, etc.)
    """
    name: str
    attribute: str
    proficiency: int = Field(default=0, ge=0, le=3)
    misc: int = 0
    example_uses: str | None = None
    notes: str | None = None


class CharacterClassEntry(BaseModel):
    """
    Inline character class record stored in the character JSON blob.
    A character can have multiple classes (multiclassing); each entry
    tracks its own level, archetype, and hit dice. The character's
    overall level is the sum of all entries' levels.

    :param name: class name (may be a GlobalClass.name or a user-custom name)
    :param archetype: optional archetype/subclass for this class
    :param level: level in this class (>=1)
    :param hit_dice: hit dice die face string (e.g. "d10"), seeded from GlobalClass at creation
    :param hit_dice_current: currently-available hit dice for this class (short-rest spend)
    :param hit_dice_max: maximum hit dice for this class (regained on long rest)
    :param saving_throw_grants: list of attribute aliases (e.g. ["STR","CON"]) this class grants save proficiency in
    :param proficiency_grants: {"weapon": [...], "armor": [...]} seeded from GlobalClass.proficiencies
    """
    name: str = "Fighter"
    archetype: str | None = None
    level: int = Field(default=1, ge=1)
    hit_dice: str | None = None
    hit_dice_current: int | None = None
    hit_dice_max: int | None = None
    saving_throw_grants: list[str] = Field(default_factory=list)
    proficiency_grants: dict[str, list[str]] = Field(default_factory=dict)


class SubAbilityEntry(BaseModel):
    """A single sub-feature/trait inside a `CharacterAbilityEntry`.

    Mirrors the catalog-side `SimpleAbility` (char_sheet_global.py): the
    parent/child shape is intentional. A Feat that grants multiple small
    effects becomes one `CharacterAbilityEntry` with several
    `SubAbilityEntry` children — one per effect. Each child can carry its
    own description and `effect` text now, and a structured
    stat-adjustment payload in the future.
    """
    name: str
    description: str = ""
    effect: str | None = None


class ResourceTracker(BaseModel):
    """Reusable use-counter for abilities and magic resource pools.

    Used as CharacterAbilityEntry.tracker (name left blank — parent has it)
    and as MagicResource.extra_resource (name set to e.g. "Sorcery Points").
    """
    name: str = ""
    current: int = 0
    maximum: int = 0
    reset_on: Literal["short", "long", "none"] = "long"


AbilityTracker = ResourceTracker
ExtraResource = ResourceTracker


class CharacterAbilityEntry(BaseModel):
    """
    A feature or ability instance on a specific character sheet.

    Catalog counterpart: `Ability` in char_sheet_global.py. The shape
    is the same — top-level container with one or more
    `SubAbilityEntry` children — but materialised per character so the
    UI can render trackers, current uses, and per-instance edits without
    touching the global rules catalog.

    :param name: the ability/feature name
    :param source: where it comes from (e.g., "Class", "Background")
    :param description: full description text
    :param sub_abilities: list of sub-traits or sub-features
    :param tracker: optional use-tracker for limited-use abilities
    """
    name: str
    source: str = ""
    description: str = ""
    sub_abilities: list[SubAbilityEntry] = Field(default_factory=list)
    tracker: AbilityTracker | None = None


class CharacterCombatManeuver(BaseModel):
    """
    A combat maneuver on a character sheet (Advanced 5e).

    :param degree: maneuver level (1-5)
    :param tradition: which tradition this maneuver belongs to
    :param exertion_cost: exertion points spent to use this maneuver
    :param action_type: "A" (action), "BA" (bonus action), "R" (reaction)
    :param stance: whether this maneuver is a stance
    """
    name: str
    degree: int = 1
    tradition: str = ""
    exertion_cost: int = 0
    action_type: str = ""
    stance: bool = False
    description: str = ""


class CharacterSpell(BaseModel):
    """
    An embedded spell entry on a character sheet. Free-form — the player types
    what they want, linked only loosely to a `MagicResource` by name.

    :param name: spell name
    :param level: spell slot level (0 = cantrip)
    :param school: legacy — kept for backward compat, not displayed
    :param description: free-form effect text
    :param casting_time: e.g. "1 action", "1 bonus action", "1 minute"
    :param duration: e.g. "Instantaneous", "1 hour"
    :param spell_range: e.g. "120 feet", "Self", "Touch"
    :param ritual: whether the spell can be cast as a ritual
    :param concentration: whether the spell requires concentration
    :param resource_name: which MagicResource fuels this spell (by name)
    :param prepared: whether the spell is currently prepared/readied
    """
    name: str
    level: int = 0
    school: str = ""
    description: str = ""
    casting_time: str = ""
    duration: str = ""
    spell_range: str = ""
    ritual: bool = False
    concentration: bool = False
    resource_name: str | None = None
    prepared: bool = False


class DarkParams(BaseModel):
    """Ultramodern5 DARK-system extras attached to a `MagicResource`.

    The dark pool itself reuses the resource's `current`/`maximum` lists
    (`current=[dark_now]`, `maximum=[vessel_base]`); this model only carries the
    misc/derived breakdown so class/ladder/feat bonuses are tracked explicitly:

    :param vessel_misc: bonus max dark capacity on top of the base vessel
    :param vr_base: Vigor Regeneration base value
    :param vr_misc: bonus to Vigor Regeneration
    :param river_misc: bonus river capacity beyond the Vigor modifier
    """
    vessel_misc: int = 0
    vr_base: int = 0
    vr_misc: int = 0
    river_misc: int = 0


class MagicResource(BaseModel):
    """
    A spellcasting resource on a character sheet (e.g. "Wizard Slots", "Warlock Pact Slots").

    The builder derives `spell_attack_total` and `spell_dc_total` from:
    - the linked `attribute` (STR/DEX/.../ or None → flat 0 mod)
    - the character's `prof_bonus`
    - per-resource `spell_attack_misc` / `spell_dc_misc` modifiers

    :param name: display name (shown on the Magic tab)
    :param source: origin (class/feat/item)
    :param magic_type: which spell-resource model applies (SLOTS/PERLEVEL/POINTS/SHADOWDARK)
    :param attribute: STR/DEX/CON/INT/WIS/CHA, or None for flat (non-attribute) casting
    :param spell_attack_misc: flat bonus added to the derived spell-attack roll
    :param spell_dc_misc: flat bonus added to the derived spell-save DC
    :param current: current value(s). PERLEVEL is a list-per-slot-level;
                    SLOTS/POINTS is a single-entry list; SHADOWDARK is None.
    :param maximum: maximum value(s); same shape rules as `current`.
    """
    name: str
    source: str = ""
    magic_type: MagicType = MagicType.PERLEVEL
    attribute: Literal["STR", "DEX", "CON", "INT", "WIS", "CHA", "VIG"] | None = None
    spell_attack_misc: int = 0
    spell_dc_misc: int = 0
    current: list[int] | None = None
    maximum: list[int] | None = None
    extra_resource: ExtraResource | None = None
    # DARK (Ultramodern5) extras — present only on magic_type == DARK resources.
    dark: DarkParams | None = None


class CharacterAction(BaseModel):
    """
    Player-maintained quick-reference action (attack, favorite spell, signature
    maneuver, etc.). Not linked to Weapons/Spells DB — free-form, so players can
    use whatever name/damage string makes sense to them.

    Derived attack_bonus / attack_dc are computed by the builder from attribute
    + proficiency + misc modifiers; toggles control whether each is displayed.

    :param name: the display name of the action
    :param attribute: STR/DEX/CON/INT/WIS/CHA (or None for pure flat-misc actions)
    :param proficient: whether proficiency bonus applies
    :param attack_misc: flat bonus added to the derived attack roll
    :param dc_misc: flat bonus added to the derived save DC
    :param show_attack_bonus: surface the computed attack bonus in the UI
    :param show_attack_dc: surface the computed save DC in the UI
    :param damage: free-form damage descriptor (e.g. "1d8 slashing")
    :param range: free-form range descriptor (e.g. "5 ft" or "20/60")
    :param notes: free-form player notes
    """
    name: str
    attribute: Literal["STR", "DEX", "CON", "INT", "WIS", "CHA", "VIG"] | None = None
    proficient: bool = False
    attack_misc: int = 0
    dc_misc: int = 0
    show_attack_bonus: bool = False
    show_attack_dc: bool = False
    damage: str = ""
    range: str = ""
    notes: str = ""


class CharacterStat(BaseModel):
    """
    This is a basic statistic for use in the character sheet.

    :param base: the base statistic
    :param misc: the misc statistic modifier
    """
    base: int
    misc: int


class CharacterProficiency(BaseModel):
    """
    This is the main holder of info for a character proficiency.

    """
    weapon: list[str]
    armor: list[str]
    language: list[str]
    instrument: list[str]
    tool: list[str]
    game: list[str]


class Race(BaseModel):
    """
    This is the main holder of info for a race.

    """
    ancestry: str  #  or heritage, race, species
    culture: str | None # or subrace like shield dwarf, hill dwarf, etc
    lineage: str | None # like dhampir


class CharacterDestiny(BaseModel):
    name: str = ""
    src_inspiration: str = ""
    inspiration_feat: str = ""
    fullfillment: str = ""


class Character(BaseModel):
    """
    This is the main holder of info for a character.

    """
    owner_id: str # FK to User
    style: SheetStyle
    name: str
    race: Race
    background: str
    #class_id: list[CharacterClass]  just query the class table for the class_id
    destiny: CharacterDestiny = Field(default_factory=CharacterDestiny)
    prof_bonus: int
    ac: CharacterStat
    initiative: CharacterStat
    inspiration: bool | None  # None in shadowdark
    conditions: list[str]
    speed: int
    size: str
    proficiency: CharacterProficiency
    experience_points: int | None = 0  # set to None for milestone Leveling

    # --- Top-bar summary fields ---
    # `classes` is the authoritative multiclass list. `character_class` and `level`
    # are denormalized display caches kept in sync by a model validator:
    #  - character_class: joined summary string (e.g. "Fighter 3 / Wizard 2", or just "Fighter" if single-class)
    #  - level: sum of all class levels
    classes: list[CharacterClassEntry] = Field(default_factory=list)
    character_class: str = "Fighter"
    level: int = 1
    hp_current: int = 10
    hp_max: int = 10
    hp_temp: int = 0
    exhaustion: int = 0  # 0-6; maps to "Exhaustion" in D&D 5e, "Fatigue" in A5e
    strife: int = 0  # 0-6; A5e only ("Strife" condition track)
    death_save_successes: int = 0  # 0-3; not used in Shadowdark
    death_save_failures: int = 0  # 0-3; not used in Shadowdark
    resistances: str = ""
    immunities: str = ""
    vulnerabilities: str = ""

    # --- Ability scores (flat breakdown for JSON blob storage) ---
    str_score: AbilityScore = Field(default_factory=AbilityScore)
    dex_score: AbilityScore = Field(default_factory=AbilityScore)
    con_score: AbilityScore = Field(default_factory=AbilityScore)
    int_score: AbilityScore = Field(default_factory=AbilityScore)
    wis_score: AbilityScore = Field(default_factory=AbilityScore)
    cha_score: AbilityScore = Field(default_factory=AbilityScore)
    # Optional 7th attribute — Ultramodern5 "Vigor" (powers the DARK magic system).
    # Always present structurally (dormant default); surfaced only when `vigor_enabled`.
    vig_score: AbilityScore = Field(default_factory=AbilityScore)

    # Per-character opt-in for the Vigor attribute (UM5). Off by default → no impact
    # on existing characters or non-UM5 styles. Gates display/seeding of VIG everywhere.
    vigor_enabled: bool = False

    # --- Inline saves, skills, abilities, actions, and inventory (stored in character JSON blob) ---
    saving_throws: list[CharacterSavingThrowSimple] = Field(default_factory=list)
    skills: list[CharacterSkillSimple] = Field(default_factory=list)
    abilities: list[CharacterAbilityEntry] = Field(default_factory=list)
    actions: list[CharacterAction] = Field(default_factory=list)
    magic_resources: list[MagicResource] = Field(default_factory=list)
    spells: list[CharacterSpell] = Field(default_factory=list)
    combat_maneuvers: list[CharacterCombatManeuver] = Field(default_factory=list)
    known_traditions: str = ""
    exertion_current: int = 0
    exertion_max: int = 0
    maneuvers_known: int = 0
    max_degree: int = 0
    maneuver_attack_misc: int = 0
    maneuver_dc_misc: int = 0
    inventory: list["InventoryItem"] = Field(default_factory=list)
    currency: dict[str, int] = Field(default_factory=dict)
    # Bonus to the base 5e-family attunement cap of 3 (feats/archetypes can raise it).
    # In the JSON blob → no migration; ignored by styles that hide attunement (Shadowdark).
    attunement_bonus: int = 0

    # --- Roleplaying description (rendered on the Description card) ---
    personality: str = ""
    ideals: str = ""
    bonds: str = ""
    flaws: str = ""
    appearance: str = ""
    backstory: str = ""

    # --- Physical / identity description ---
    age: str = ""
    gender: str = ""
    height: str = ""
    weight: str = ""
    eyes: str = ""
    hair: str = ""
    skin: str = ""
    alignment: str = ""
    title: str = ""
    deity: str = ""

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if isinstance(data.get("destiny"), str):
            data["destiny"] = {"name": data["destiny"]}
        for cm in data.get("combat_maneuvers", []) or []:
            if isinstance(cm, dict):
                cm.pop("exertion_current", None)
                cm.pop("exertion_max", None)
        return data

    @model_validator(mode="after")
    def _sync_classes_and_level(self) -> "Character":
        """Keep `classes`, `character_class`, and `level` coherent.

        - If `classes` is empty, bootstrap a single entry from the legacy
          `character_class` + `level` fields (supports older stored JSON blobs).
        - If `classes` is non-empty, overwrite `character_class` (joined summary)
          and `level` (sum of class levels) from the list.
        """
        if not self.classes:
            self.classes = [CharacterClassEntry(
                name=self.character_class or "Fighter",
                level=max(self.level or 1, 1),
            )]

        # Sync display cache
        if len(self.classes) == 1:
            only = self.classes[0]
            self.character_class = only.name
        else:
            self.character_class = " / ".join(f"{c.name} {c.level}" for c in self.classes)
        self.level = sum(c.level for c in self.classes)
        return self


class InventoryItem(BaseModel):
    """
    A single item in the character's inventory, stored inline in the character JSON blob.
    Display metadata (damage, AC, weight, etc.) is denormalized from the global tables at
    add-time so the sheet renders without extra DB queries.

    :param item_type: "weapon", "armor", or "item"
    :param name: display name
    :param quantity: how many the character carries
    :param equipped: whether currently equipped
    :param attuned: whether currently attuned (magic items)
    :param notes: player-written notes
    :param damage: weapon damage dice (e.g. "1d8")
    :param damage_type: weapon damage type (e.g. "slashing")
    :param weapon_range: weapon range (avoids shadowing Python builtin)
    :param armor_class: armor AC value string
    :param weight: item weight
    :param value: item cost/value
    :param item_notes: properties/notes from global table (e.g. "Finesse, light")
    :param is_custom: True if the entry was authored or edited by the player —
        i.e. has diverged from any library template. False on pristine snapshots
        added via "Add from Library". Set on the Add-Custom path and on every
        successful inventory edit.
    """
    item_type: str  # "weapon", "armor", "item"
    name: str
    quantity: int = 1
    equipped: bool = False
    attuned: bool = False
    notes: str = ""
    # Denormalized display fields
    damage: str | None = None
    damage_type: str | None = None
    weapon_range: str | None = None
    armor_class: str | None = None
    # Numeric AC breakdown — copied off GlobalArmor at add-time so the sheet's
    # AC math doesn't need another DB round-trip. None on non-armor items.
    base_ac: int | None = None
    dex_cap: int | None = None
    is_shield: bool = False
    weight: str | None = None
    value: str | None = None
    item_notes: str | None = None
    # Optional soft link to a `CharacterAlly.id` on the Allies & Stat Blocks tab
    # (used by Vehicles, Drones, Mounts, Pets seeded at add-time).
    ally_id: str | None = None
    is_custom: bool = False


# Resolve forward reference
Character.model_rebuild()

