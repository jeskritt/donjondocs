"""Integration tests for Shadowrun: Anarchy 2.0 services, JSON ingest, passwordless backups, and Admin services."""

from pathlib import Path

import pytest

from app.cli.ingest import run_ingestion_in_session
from app.models.user import User
from app.rule_systems import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.security import verify_password
from app.services._errors import CharacterServiceError
from app.services.admin_service import (
    AdminServiceError,
    create_verified_admin_backup,
    get_global_table_stats,
    reseed_global_data,
    reset_backup_rate_limit,
)
from app.services.backup_service import (
    LOCKED_PASSWORD_SENTINEL,
    RestoreMode,
    create_backup,
    restore_backup,
)
from app.services.character_service import (
    create_character,
    export_character,
    import_character,
    rest_character,
    update_character,
)
from app.services.global_items_service import (
    list_abilities,
    list_armor,
    list_items,
    list_skills,
    list_spells,
    list_weapons,
)
from app.user_context import UserContext


REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


async def test_create_update_reset_and_export_import_anarchy(db_session, test_user):
    owner = UserContext.from_user(test_user)
    rec = await create_character(
        db_session,
        name="Nyx",
        style=SheetStyle.SHADOWRUN_ANARCHY_2,
        current_user=owner,
        metatype="Elf",
        keywords=["Elf", "Seattle", "Shaman", "Low Lifestyle", "Ex-Corp"],
    )
    assert rec.style == SheetStyle.SHADOWRUN_ANARCHY_2
    assert rec.character_data["metatype"] == "Elf"
    assert rec.character_data["edge_base"] == 3
    assert rec.character_data["edge_current"] == 3
    assert len(rec.character_data["skills"]) == 14

    # Spend Edge & take wounds, then verify new_run and heal_all resets.
    rec = await update_character(
        db_session,
        rec.id,
        {
            "edge_current": 1,
            "wounds": {"light": [True, False], "serious": [True], "incapacitated": False, "stim_patch_active": True},
        },
        owner,
    )
    rec = await rest_character(db_session, rec.id, "new_run", {}, owner)
    assert rec.character_data["edge_current"] == 3
    assert rec.character_data["wounds"]["stim_patch_active"] is False

    rec = await rest_character(db_session, rec.id, "heal_all", {}, owner)
    assert rec.character_data["wounds"]["light"] == [False, False]
    assert rec.character_data["wounds"]["serious"] == [False]

    # 5e rest kinds must be rejected on Anarchy characters.
    with pytest.raises(CharacterServiceError):
        await rest_character(db_session, rec.id, "short", {}, owner)

    # Export & re-import round-trip.
    envelope = await export_character(db_session, rec.id, owner)
    assert envelope["style"] == SheetStyle.SHADOWRUN_ANARCHY_2.value
    imported = await import_character(
        db_session,
        name="Nyx Copy",
        style=SheetStyle(envelope["style"]),
        character_data=envelope["character_data"],
        current_user=owner,
        version=envelope["version"],
    )
    assert imported.id != rec.id
    assert imported.character_data["metatype"] == "Elf"
    # Ensure 5e fields were NOT injected by 5e migrators.
    assert "death_save_successes" not in imported.character_data


async def test_ingest_sra2_json_catalogs_is_idempotent(db_session, test_user):
    report1 = await run_ingestion_in_session(db_session, str(REPO_DATA_DIR / "sra2"))
    assert report1["files"] == 7
    assert report1["inserted"] > 80

    # Second run updates in place with zero duplicates.
    report2 = await run_ingestion_in_session(db_session, str(REPO_DATA_DIR / "sra2"))
    assert report2["inserted"] == 0
    assert report2["updated"] == report1["inserted"]

    skills = await list_skills(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id)
    weapons = await list_weapons(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id)
    armor = await list_armor(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id)
    items = await list_items(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id)
    spells = await list_spells(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id)
    amps = await list_abilities(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id)

    assert len(skills) == 14
    assert len(weapons) >= 20
    assert len(armor) == 6
    assert len(items) >= 10
    assert len(spells) >= 30
    assert any("MCT 360" in a.name for a in amps)
    assert any("Harley-Davidson Centaur" in a.name for a in amps)


async def test_mixed_5e_and_anarchy_backup_and_passwordless_restore(db_session, test_user):
    owner = UserContext.from_user(test_user)
    user_id = test_user.id
    original_hash = test_user.hashed_password

    await create_character(
        db_session,
        name="Fighter One",
        style=SheetStyle.DND5E,
        current_user=owner,
        classes=[CharacterClassEntry(name="Fighter", level=1)],
    )
    await create_character(
        db_session,
        name="Runner One",
        style=SheetStyle.SHADOWRUN_ANARCHY_2,
        current_user=owner,
        metatype="Troll",
    )

    # Passwordless backup omits hashed_password from users.
    env = await create_backup(db_session, include_passwords=False)
    assert env.includes_passwords is False
    assert all("hashed_password" not in u for u in env.users)
    assert len(env.characters) == 2

    # MERGE restore preserves existing user password hash.
    report_merge = await restore_backup(db_session, env, mode=RestoreMode.MERGE, force=True)
    assert report_merge.characters_updated == 2
    refreshed = await db_session.get(User, user_id)
    assert refreshed.hashed_password == original_hash

    # REPLACE restore inserts passwordless users with an unmatchable locked sentinel.
    report_replace = await restore_backup(db_session, env, mode=RestoreMode.REPLACE, force=True)
    assert report_replace.users_inserted == 1
    assert report_replace.characters_inserted == 2
    db_session.expire_all()
    replaced_user = await db_session.get(User, user_id)
    assert replaced_user.hashed_password == LOCKED_PASSWORD_SENTINEL
    assert verify_password("TestPass123!", replaced_user.hashed_password) is False


async def test_admin_service_reseed_stats_and_verified_backup_guardrails(
    db_session, test_admin, test_user
):
    reset_backup_rate_limit()
    admin_ctx = UserContext.from_user(test_admin)
    std_ctx = UserContext.from_user(test_user)

    # Non-admins are blocked from every admin service operation.
    with pytest.raises(AdminServiceError) as exc_info:
        await get_global_table_stats(db_session, std_ctx)
    assert exc_info.value.status_code == 403

    with pytest.raises(AdminServiceError):
        await reseed_global_data(db_session, std_ctx, data_dir=REPO_DATA_DIR / "sra2")

    with pytest.raises(AdminServiceError):
        await create_verified_admin_backup(db_session, std_ctx, "TestPass123!")

    # Admin reseed & stats work cleanly, streaming progress callbacks per file.
    progress_events: list[tuple[int, int, str]] = []
    report = await reseed_global_data(
        db_session,
        admin_ctx,
        data_dir=REPO_DATA_DIR / "sra2",
        on_progress=lambda c, t, lbl, _rep: progress_events.append((c, t, lbl)),
    )
    assert report["inserted"] > 80
    # 7 JSON files + 1 final "Committing to database…" tick
    assert len(progress_events) == report["files"] + 1
    assert progress_events[-1][0] == report["files"]
    stats = await get_global_table_stats(db_session, admin_ctx)
    sra2_row = next(r for r in stats if r["source"] == SheetStyle.SHADOWRUN_ANARCHY_2.value)
    assert sra2_row["skills"] == 14
    assert sra2_row["spells"] >= 30
    assert sra2_row["abilities"] >= 40

    # Wrong password rejected (401).
    with pytest.raises(AdminServiceError) as exc_pw:
        await create_verified_admin_backup(db_session, admin_ctx, "WrongPassword!")
    assert exc_pw.value.status_code == 401

    # Valid password succeeds twice, then hits the 2/hour rate limit (429).
    fn1, payload1, summary1 = await create_verified_admin_backup(
        db_session, admin_ctx, "TestPass123!", include_passwords=False
    )
    assert "nopasswords" in fn1
    assert b"hashed_password" not in payload1
    assert summary1["users"] >= 2

    fn2, payload2, _ = await create_verified_admin_backup(
        db_session, admin_ctx, "TestPass123!", include_passwords=True
    )
    assert "full" in fn2
    assert b"hashed_password" in payload2

    with pytest.raises(AdminServiceError) as exc_rl:
        await create_verified_admin_backup(db_session, admin_ctx, "TestPass123!", include_passwords=False)
    assert exc_rl.value.status_code == 429
    reset_backup_rate_limit()
