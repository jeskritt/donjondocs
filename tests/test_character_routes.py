"""Integration tests for character REST routes."""

import io
import json

import pytest

from app.api.character_routes import MAX_IMPORT_BYTES
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.services.character_service import create_character
from tests.conftest import auth_cookies


@pytest.mark.asyncio
class TestRestEndpoint:
    """POST /api/characters/{id}/rest — short/long rest with RBAC."""

    async def _make_char(self, db_session, user):
        char = await create_character(
            db_session, "Restee", SheetStyle.DND5E, user,
            classes=[CharacterClassEntry(name="Fighter", level=3)],
        )
        # Simulate damage to verify long rest restores HP
        data = dict(char.character_data)
        data["hp_current"] = 1
        char.character_data = data
        await db_session.commit()
        await db_session.refresh(char)
        return char

    async def test_long_rest_restores_hp(self, client, db_session, test_user):
        char = await self._make_char(db_session, test_user)
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            f"/api/characters/{char.id}/rest",
            json={"kind": "long", "options": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["hp_current"] == body["hp_max"]

    async def test_unauthenticated_rejected(self, client, db_session, test_user):
        char = await self._make_char(db_session, test_user)
        resp = await client.post(
            f"/api/characters/{char.id}/rest",
            json={"kind": "long", "options": {}},
        )
        assert resp.status_code == 401

    async def test_other_user_forbidden(self, client, db_session, test_user, test_premium):
        char = await self._make_char(db_session, test_user)
        client.cookies = auth_cookies(test_premium)
        resp = await client.post(
            f"/api/characters/{char.id}/rest",
            json={"kind": "long", "options": {}},
        )
        assert resp.status_code == 403

    async def test_admin_can_rest_any(self, client, db_session, test_user, test_admin):
        char = await self._make_char(db_session, test_user)
        client.cookies = auth_cookies(test_admin)
        resp = await client.post(
            f"/api/characters/{char.id}/rest",
            json={"kind": "long", "options": {}},
        )
        assert resp.status_code == 200

    async def test_bad_kind_rejected(self, client, db_session, test_user):
        char = await self._make_char(db_session, test_user)
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            f"/api/characters/{char.id}/rest",
            json={"kind": "nap", "options": {}},
        )
        # Pydantic Literal rejects → 422
        assert resp.status_code == 422


async def _good_envelope(db_session, owner, name: str = "Imported") -> dict:
    """Build a real export envelope via create + export.

    The Character schema is wide enough that hand-rolling a minimal blob
    is brittle; round-tripping a freshly-created character keeps these
    tests resilient to schema additions.
    """
    from app.services.character_service import export_character
    char = await create_character(
        db_session, name, SheetStyle.DND5E, owner,
        classes=[CharacterClassEntry(name="Fighter", level=1)],
    )
    return await export_character(db_session, char.id, owner)


def _upload(envelope_bytes: bytes, filename: str = "char.json") -> dict:
    """Build the multipart-files dict httpx expects."""
    return {"file": (filename, io.BytesIO(envelope_bytes), "application/json")}


@pytest.mark.asyncio
class TestImportEndpoint:
    """POST /api/characters/import — file upload, size limit, validation."""

    async def test_valid_import_creates_character(self, client, db_session, test_user):
        env = await _good_envelope(db_session, test_user, "Valid")
        envelope = json.dumps(env, default=str).encode()
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            "/api/characters/import",
            files=_upload(envelope),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Valid"
        assert body["id"]

    async def test_oversized_file_rejected(self, client, db_session, test_user):
        # Pad the envelope to push raw bytes past the cap.
        env = await _good_envelope(db_session, test_user, "Big")
        env["padding"] = "x" * (MAX_IMPORT_BYTES + 1024)
        envelope = json.dumps(env, default=str).encode()
        assert len(envelope) > MAX_IMPORT_BYTES
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            "/api/characters/import",
            files=_upload(envelope),
        )
        assert resp.status_code == 413
        assert "exceeds" in resp.json()["detail"]

    async def test_non_json_filename_rejected(self, client, db_session, test_user):
        env = await _good_envelope(db_session, test_user)
        envelope = json.dumps(env, default=str).encode()
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            "/api/characters/import",
            files=_upload(envelope, filename="char.txt"),
        )
        assert resp.status_code == 400
        assert ".json" in resp.json()["detail"]

    async def test_invalid_json_rejected(self, client, test_user):
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            "/api/characters/import",
            files=_upload(b"not json {{{"),
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

    async def test_missing_character_data_rejected(self, client, test_user):
        envelope = json.dumps(
            {"version": 3, "name": "X", "style": SheetStyle.DND5E.value}
        ).encode()
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            "/api/characters/import",
            files=_upload(envelope),
        )
        assert resp.status_code == 400
        assert "character_data" in resp.json()["detail"]

    async def test_unknown_style_rejected(self, client, db_session, test_user):
        env = await _good_envelope(db_session, test_user)
        env["style"] = "homebrew_xyz"
        client.cookies = auth_cookies(test_user)
        resp = await client.post(
            "/api/characters/import",
            files=_upload(json.dumps(env, default=str).encode()),
        )
        assert resp.status_code == 400
        assert "Unknown style" in resp.json()["detail"]

    async def test_unauthenticated_rejected(self, client, db_session, test_user):
        env = await _good_envelope(db_session, test_user)
        envelope = json.dumps(env, default=str).encode()
        resp = await client.post(
            "/api/characters/import",
            files=_upload(envelope),
        )
        assert resp.status_code == 401
