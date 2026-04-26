"""
AI Helper Docstring
Purpose: Lookup + custom-creation surface across the `Global*` reference tables (weapons, armor, items, classes, skills, attributes, destinies). Applies the seeded-vs-custom scoping rule: `owner_id IS NULL` rows are visible to all, plus the caller's own `owner_id` rows.
Interactions:
- `app.models.char_sheet`: every `Global*` ORM class.
- `app.schemas.char_sheet_global`: `Custom*Input` shapes for user-defined entries.
- `app.ui.pages.character_sheet` and `app.ui.pages.sheet_creator`: dropdowns and "Add custom..." dialogs.
- `app.cli.ingest`: populates the `owner_id IS NULL` baseline at startup if any table is empty.
"""

import uuid
from typing import Sequence

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.char_sheet import (
    GlobalWeapon, GlobalArmor, GlobalItem,
    GlobalClass, GlobalSkill, GlobalAttribute,
    GlobalDestiny,
)
from app.schemas.char_sheet_global import SheetStyle, CustomWeaponInput, CustomArmorInput, CustomItemInput


async def _list_global(
    session: AsyncSession,
    model_cls,
    style: SheetStyle,
    owner_id: str | None = None,
) -> Sequence:
    stmt = select(model_cls).where(
        model_cls.source == style.value,
    ).where(
        or_(
            model_cls.owner_id.is_(None),
            model_cls.owner_id == owner_id,
        )
    ).order_by(model_cls.name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_weapons(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalWeapon]:
    return await _list_global(session, GlobalWeapon, style, owner_id)


async def list_armor(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalArmor]:
    return await _list_global(session, GlobalArmor, style, owner_id)


async def list_items(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalItem]:
    return await _list_global(session, GlobalItem, style, owner_id)


async def list_classes(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalClass]:
    return await _list_global(session, GlobalClass, style, owner_id)


async def list_skills(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalSkill]:
    return await _list_global(session, GlobalSkill, style, owner_id)


async def list_attributes(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalAttribute]:
    return await _list_global(session, GlobalAttribute, style, owner_id)


async def list_destinies(session: AsyncSession, style: SheetStyle, owner_id: str | None = None) -> Sequence[GlobalDestiny]:
    return await _list_global(session, GlobalDestiny, style, owner_id)


async def add_custom_weapon(
    session: AsyncSession,
    owner_id: str,
    style: SheetStyle,
    data: CustomWeaponInput,
) -> GlobalWeapon:
    w = GlobalWeapon(
        id=str(uuid.uuid4()),
        name=data.name,
        type=data.weapon_type,
        damage=data.damage,
        damage_type=data.damage_type,
        range=data.weapon_range,
        weight=data.weight,
        value=data.value,
        notes=data.notes,
        source=style.value,
        owner_id=owner_id,
    )
    session.add(w)
    await session.commit()
    await session.refresh(w)
    return w


async def add_custom_armor(
    session: AsyncSession,
    owner_id: str,
    style: SheetStyle,
    data: CustomArmorInput,
) -> GlobalArmor:
    a = GlobalArmor(
        id=str(uuid.uuid4()),
        name=data.name,
        type=data.armor_type,
        armor_class=data.armor_class,
        strength_requirement=data.strength_requirement,
        weight=data.weight,
        value=data.value,
        notes=data.notes,
        source=style.value,
        owner_id=owner_id,
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


async def add_custom_item(
    session: AsyncSession,
    owner_id: str,
    style: SheetStyle,
    data: CustomItemInput,
) -> GlobalItem:
    i = GlobalItem(
        id=str(uuid.uuid4()),
        name=data.name,
        type=data.item_type,
        weight=data.weight,
        value=data.value,
        effects=data.effects,
        source=style.value,
        owner_id=owner_id,
    )
    session.add(i)
    await session.commit()
    await session.refresh(i)
    return i


async def add_custom_class(
    session: AsyncSession,
    owner_id: str,
    style: SheetStyle,
    name: str,
    hit_dice: str = "",
    primary_ability: str = "",
    saving_throws: str = "",
    proficiencies: str = "",
    description: str = "",
) -> GlobalClass:
    c = GlobalClass(
        id=str(uuid.uuid4()),
        name=name,
        hit_dice=hit_dice,
        primary_ability=primary_ability,
        saving_throws=saving_throws,
        proficiencies=proficiencies,
        description=description,
        source=style.value,
        owner_id=owner_id,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c
