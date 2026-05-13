"""
AI Helper Docstring
Purpose: Integration tests for the Creature REST routes. Exercises auth + serialization end-to-end: list visibility, owner-only edit/delete, the copy-and-reset-public contract, parse endpoint result shape, and the import-resets-public guarantee.
Interactions:
- Targets routes registered at `/api/creatures` by `app.api.creature_routes`.
- Uses the conftest `client` and `auth_cookies` helpers.
"""

import io
import json

import pytest
from httpx import AsyncClient

from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_create_then_list(client: AsyncClient, test_user):
    r = await client.post(
        "/api/creatures",
        json={"name": "Goblin", "creature_type": "Humanoid", "size": "Small"},
        cookies=auth_cookies(test_user),
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["name"] == "Goblin"
    assert created["owner_id"] == test_user.id
    assert created["owner_username"] == test_user.username

    r = await client.get("/api/creatures", cookies=auth_cookies(test_user))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_list_omits_other_users_private(
    client: AsyncClient, test_user, create_test_user
):
    other = await create_test_user(username="other", email="o@t.com")
    await client.post(
        "/api/creatures",
        json={"name": "Hidden"},
        cookies=auth_cookies(other),
    )
    r = await client.get("/api/creatures", cookies=auth_cookies(test_user))
    assert r.json() == []


@pytest.mark.asyncio
async def test_public_creature_visible_to_other(
    client: AsyncClient, test_user, create_test_user
):
    other = await create_test_user(username="other", email="o@t.com")
    created = (await client.post(
        "/api/creatures",
        json={"name": "Shared", "is_public": True},
        cookies=auth_cookies(other),
    )).json()
    r = await client.get("/api/creatures", cookies=auth_cookies(test_user))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == created["id"]
    assert rows[0]["owner_username"] == "other"


@pytest.mark.asyncio
async def test_non_owner_cannot_edit(
    client: AsyncClient, test_user, create_test_user
):
    other = await create_test_user(username="other", email="o@t.com")
    created = (await client.post(
        "/api/creatures",
        json={"name": "Pub", "is_public": True},
        cookies=auth_cookies(other),
    )).json()
    r = await client.patch(
        f"/api/creatures/{created['id']}",
        json={"name": "Hacked"},
        cookies=auth_cookies(test_user),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_copy_resets_public_and_owner(
    client: AsyncClient, test_user, create_test_user
):
    other = await create_test_user(username="other", email="o@t.com")
    src = (await client.post(
        "/api/creatures",
        json={"name": "Source", "is_public": True, "creature_type": "Beast"},
        cookies=auth_cookies(other),
    )).json()
    r = await client.post(
        f"/api/creatures/{src['id']}/copy",
        cookies=auth_cookies(test_user),
    )
    assert r.status_code == 201
    copy = r.json()
    assert copy["owner_id"] == test_user.id
    assert copy["is_public"] is False
    assert copy["creature_type"] == "Beast"
    assert copy["id"] != src["id"]


@pytest.mark.asyncio
async def test_parse_endpoint(client: AsyncClient, test_user):
    body = (
        "___\n> ## Goblin\n> *Small humanoid, neutral evil*\n> ___\n"
        "> *Challenge* 1/4 (50 XP)\n"
    )
    created = (await client.post(
        "/api/creatures",
        json={"name": "Goblin", "body_md": body},
        cookies=auth_cookies(test_user),
    )).json()
    r = await client.post(
        f"/api/creatures/{created['id']}/parse",
        cookies=auth_cookies(test_user),
    )
    assert r.status_code == 200
    parsed = r.json()
    assert parsed["size"] == "Small"
    assert parsed["creature_type"] == "Humanoid"
    assert parsed["challenge_rating"] == "1/4"


@pytest.mark.asyncio
async def test_export_then_import_resets_public(client: AsyncClient, test_user):
    """Export a public creature, then import — the import must reset
    is_public to False so the importer opts into sharing explicitly."""
    created = (await client.post(
        "/api/creatures",
        json={"name": "PublicMonster", "is_public": True},
        cookies=auth_cookies(test_user),
    )).json()

    r = await client.get(
        f"/api/creatures/{created['id']}/export",
        cookies=auth_cookies(test_user),
    )
    assert r.status_code == 200
    envelope = json.loads(r.content)
    # Envelope shape sanity
    assert envelope["version"] >= 1
    assert envelope["creature_data"]["name"] == "PublicMonster"

    # Hand-craft the import: the envelope's creature_data may say is_public=true
    # but the importer must zero it.
    envelope["creature_data"]["is_public"] = True
    raw = json.dumps(envelope).encode()
    files = {"file": ("creature.json", io.BytesIO(raw), "application/json")}
    r = await client.post(
        "/api/creatures/import",
        files=files,
        cookies=auth_cookies(test_user),
    )
    assert r.status_code == 201, r.text
    imported = r.json()
    assert imported["is_public"] is False
    assert imported["name"] == "PublicMonster"


@pytest.mark.asyncio
async def test_filter_by_type_substring(client: AsyncClient, test_user):
    """The list endpoint accepts q/type/size narrowing params."""
    await client.post(
        "/api/creatures",
        json={"name": "A1", "creature_type": "Beast"},
        cookies=auth_cookies(test_user),
    )
    await client.post(
        "/api/creatures",
        json={"name": "B1", "creature_type": "Undead"},
        cookies=auth_cookies(test_user),
    )
    r = await client.get(
        "/api/creatures",
        params={"type": "Undead"},
        cookies=auth_cookies(test_user),
    )
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "B1"
