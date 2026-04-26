"""
AI Helper Docstring
Purpose: SQLAlchemy ORM tracking the global database records (Items, Rules, Spells) that define all the varied RPG rule structures. 
Interactions:
- `app.database.py`: Binds explicitly to the `Base` declarative object.
- `app.cli.ingest.py`: Utilized as the ultimate destination for incoming dataset uploads.
"""

import uuid
from typing import Optional
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

def generate_uuid() -> str:
    return str(uuid.uuid4())

class GlobalAbility(Base, TimestampMixin):
    __tablename__ = "global_ability"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_ability_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    features: Mapped[Optional[str]] = mapped_column(String, nullable=True) # JSON list or comma separated
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)


class GlobalClass(Base, TimestampMixin):
    __tablename__ = "global_class"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_class_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hit_dice: Mapped[str] = mapped_column(String)
    primary_ability: Mapped[str] = mapped_column(String)
    saving_throws: Mapped[str] = mapped_column(String)
    proficiencies: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)


class GlobalAttribute(Base, TimestampMixin):
    __tablename__ = "global_attribute"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_attribute_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    alias: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)


class GlobalSkill(Base, TimestampMixin):
    __tablename__ = "global_skill"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_skill_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    # example_uses replaces a generic "description" field: skill entries in the
    # rulebook list example in-play uses rather than a definition paragraph.
    example_uses: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    specialties: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    attribute: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)


class GlobalItem(Base, TimestampMixin):
    __tablename__ = "global_item"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_item_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    weight: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effects: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_container: Mapped[bool] = mapped_column(Boolean, default=False)
    is_equipable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_consumable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_attunable: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)

class GlobalWeapon(Base, TimestampMixin):
    __tablename__ = "global_weapon"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_weapon_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    damage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    damage_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    range: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    weight: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effects: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)

class GlobalArmor(Base, TimestampMixin):
    __tablename__ = "global_armor"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_armor_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    armor_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Numeric breakdown driving AC computation. base_ac is the armor's flat
    # contribution (e.g. 11 for Leather, 18 for Plate, or a shield bonus like 2).
    # dex_cap is the max DEX mod the wearer can add (None = uncapped/Light).
    # is_shield flips the semantics: base_ac becomes a flat +N bonus layered on
    # top of whatever else is equipped.
    base_ac: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dex_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_shield: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strength_requirement: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    disadvantage_on_stealth: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    weight: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effects: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)

class GlobalCombatManeuver(Base, TimestampMixin):
    __tablename__ = "global_combat_maneuver"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_combat_maneuver_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tradition: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    exertion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    activation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)

class GlobalSpell(Base, TimestampMixin):
    __tablename__ = "global_spell"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_spell_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    school: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    classes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    casting_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    range: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    components: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ritual: Mapped[bool] = mapped_column(Boolean, default=False)
    concentration: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)

class GlobalDestiny(Base, TimestampMixin):
    __tablename__ = "global_destiny"
    __table_args__ = (
        UniqueConstraint('name', 'source', 'owner_id', name='uq_global_destiny_name_source_owner'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    src_inspiration: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inspiration_feat: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fullfillment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
