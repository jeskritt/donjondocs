"""
AI Helper Docstring
Purpose: Service-layer tests for the Creature catalog. Covers CRUD happy path, visibility filter (own + public, never others' private), owner/admin RBAC on edit and delete, and the copy contract (new owner, is_public always reset to False).
Interactions:
- Targets `app.services.creature_service.*`.
- Reuses conftest fixtures `db_session`, `create_test_user`, `test_admin`, `test_user`.
"""

import pytest

from app.models.creature import Creature
from app.schemas.creature import CreatureCreate, CreatureUpdate
from app.services._errors import CreatureServiceError
from app.services.creature_service import (
    copy_creature,
    create_creature,
    delete_creature,
    get_creature,
    list_creatures_visible_to,
    update_creature,
)
from app.user_context import UserContext


async def _make(db_session, owner_id, *, name="X", is_public=False, **kw):
    """Tiny factory — bypass the service so tests can plant arbitrary rows."""
    fields = {
        "owner_id": owner_id, "name": name, "body_md": "", "creature_type": "",
        "size": "", "challenge_rating": "", "habitat": "Any",
        "is_public": is_public, "columns": 1,
    }
    fields.update(kw)
    c = Creature(**fields)
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest.mark.asyncio
async def test_create_sets_owner(db_session, test_user):
    ctx = UserContext.from_user(test_user)
    row = await create_creature(db_session, ctx, CreatureCreate(name="Goblin"))
    assert row.owner_id == test_user.id
    assert row.is_public is False


@pytest.mark.asyncio
async def test_list_visibility(db_session, create_test_user, test_user):
    """User sees own creatures + public creatures, never others' private ones."""
    mine = await _make(db_session, test_user.id, name="Mine Private")
    mine_pub = await _make(db_session, test_user.id, name="Mine Public", is_public=True)
    other = await create_test_user(username="other", email="o@t.com")
    other_priv = await _make(db_session, other.id, name="Their Private")
    other_pub = await _make(db_session, other.id, name="Their Public", is_public=True)

    visible = await list_creatures_visible_to(db_session, UserContext.from_user(test_user))
    visible_ids = {r.id for r in visible}
    assert mine.id in visible_ids
    assert mine_pub.id in visible_ids
    assert other_pub.id in visible_ids
    assert other_priv.id not in visible_ids


@pytest.mark.asyncio
async def test_get_other_private_403(db_session, create_test_user, test_user):
    other = await create_test_user(username="other", email="o@t.com")
    priv = await _make(db_session, other.id, name="Hidden")
    with pytest.raises(CreatureServiceError) as exc:
        await get_creature(db_session, priv.id, UserContext.from_user(test_user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_only_owner(db_session, create_test_user, test_user):
    other = await create_test_user(username="other", email="o@t.com")
    foreign = await _make(db_session, other.id, name="Foreign", is_public=True)
    with pytest.raises(CreatureServiceError) as exc:
        await update_creature(
            db_session, foreign.id,
            CreatureUpdate(name="Hacked"),
            UserContext.from_user(test_user),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_edit_others(db_session, create_test_user, test_admin):
    standard = await create_test_user(username="s", email="s@t.com")
    row = await _make(db_session, standard.id, name="Owned by user")
    updated = await update_creature(
        db_session, row.id,
        CreatureUpdate(name="Edited by admin"),
        UserContext.from_user(test_admin),
    )
    assert updated.name == "Edited by admin"


@pytest.mark.asyncio
async def test_copy_resets_public_and_owner(db_session, create_test_user, test_user):
    """Anyone who can view a creature can copy it; the copy lands private,
    owned by the copier — regardless of the source's visibility."""
    other = await create_test_user(username="other", email="o@t.com")
    source = await _make(
        db_session, other.id, name="Shared Pet", is_public=True,
        creature_type="Beast", size="Small", body_md="..."
    )
    copy = await copy_creature(
        db_session, source.id, UserContext.from_user(test_user)
    )
    assert copy.owner_id == test_user.id
    assert copy.is_public is False
    # Body + metadata copied
    assert copy.body_md == source.body_md
    assert copy.creature_type == source.creature_type
    # Different id
    assert copy.id != source.id


@pytest.mark.asyncio
async def test_copy_requires_visibility(db_session, create_test_user, test_user):
    """Can't copy something you can't see."""
    other = await create_test_user(username="other", email="o@t.com")
    hidden = await _make(db_session, other.id, name="Hidden")
    with pytest.raises(CreatureServiceError) as exc:
        await copy_creature(db_session, hidden.id, UserContext.from_user(test_user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_owner_only(db_session, create_test_user, test_user):
    other = await create_test_user(username="other", email="o@t.com")
    foreign = await _make(db_session, other.id, name="Foreign", is_public=True)
    with pytest.raises(CreatureServiceError) as exc:
        await delete_creature(db_session, foreign.id, UserContext.from_user(test_user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_diff_only_sets_provided_fields(db_session, test_user):
    """The partial-update contract — fields not in the payload aren't touched."""
    row = await _make(
        db_session, test_user.id, name="Original",
        creature_type="Beast", size="Medium", challenge_rating="1",
    )
    await update_creature(
        db_session, row.id,
        CreatureUpdate(name="Renamed"),
        UserContext.from_user(test_user),
    )
    await db_session.refresh(row)
    assert row.name == "Renamed"
    assert row.creature_type == "Beast"
    assert row.size == "Medium"
    assert row.challenge_rating == "1"
