"""
Tests for CharacterService CRUD operations and RBAC enforcement.

Validates:
- User-scoped listing
- Ownership / admin access checks on get/update/delete
- Standard user creation limit (25)
- Character name sync on update
"""

import pytest
import pytest_asyncio

from app.models.character import CharacterRecord
from app.models.user import User, UserRole
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.services.character_service import (
    CharacterServiceError,
    apply_rest,
    create_character,
    delete_character,
    export_character,
    get_character,
    import_character,
    list_user_characters,
    rest_character,
    update_character,
)
from app.security import hash_password


def _default_classes() -> list[CharacterClassEntry]:
    """Minimal single-class Fighter entry for tests that don't care about class specifics."""
    return [CharacterClassEntry(name="Fighter", level=1)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_user(db_session) -> User:
    user = User(
        username="char_admin",
        email="char_admin@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def standard_user(db_session) -> User:
    user = User(
        username="char_std",
        email="char_std@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.STANDARD,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def premium_user(db_session) -> User:
    user = User(
        username="char_premium",
        email="char_premium@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.PREMIUM,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_character(db_session, standard_user) -> CharacterRecord:
    """Pre-create a character owned by the standard user."""
    char = await create_character(
        db_session, "Tharivol", SheetStyle.DND5E, standard_user,
        classes=_default_classes(),
    )
    return char


# ---------------------------------------------------------------------------
# list_user_characters
# ---------------------------------------------------------------------------

class TestListUserCharacters:
    @pytest.mark.asyncio
    async def test_returns_only_own_characters(self, db_session, standard_user, premium_user):
        await create_character(db_session, "Owned1", SheetStyle.DND5E, standard_user, classes=_default_classes())
        await create_character(db_session, "Owned2", SheetStyle.A5E, standard_user, classes=_default_classes())
        await create_character(db_session, "OtherUser", SheetStyle.SHADOWDARK, premium_user, classes=_default_classes())

        chars = await list_user_characters(db_session, standard_user.id)
        assert len(chars) == 2
        assert all(c.owner_id == standard_user.id for c in chars)

    @pytest.mark.asyncio
    async def test_empty_list_for_new_user(self, db_session, premium_user):
        chars = await list_user_characters(db_session, premium_user.id)
        assert chars == [] or len(chars) == 0


# ---------------------------------------------------------------------------
# get_character
# ---------------------------------------------------------------------------

class TestGetCharacter:
    @pytest.mark.asyncio
    async def test_owner_can_access(self, db_session, standard_user, sample_character):
        char = await get_character(db_session, sample_character.id, standard_user)
        assert char.id == sample_character.id
        assert char.name == "Tharivol"

    @pytest.mark.asyncio
    async def test_admin_can_access_any(self, db_session, admin_user, sample_character):
        char = await get_character(db_session, sample_character.id, admin_user)
        assert char.id == sample_character.id

    @pytest.mark.asyncio
    async def test_other_user_denied(self, db_session, premium_user, sample_character):
        with pytest.raises(CharacterServiceError, match="Access denied"):
            await get_character(db_session, sample_character.id, premium_user)

    @pytest.mark.asyncio
    async def test_not_found(self, db_session, standard_user):
        with pytest.raises(CharacterServiceError, match="not found"):
            await get_character(db_session, "nonexistent-id", standard_user)


# ---------------------------------------------------------------------------
# create_character
# ---------------------------------------------------------------------------

class TestCreateCharacter:
    @pytest.mark.asyncio
    async def test_standard_user_creates(self, db_session, standard_user):
        char = await create_character(db_session, "NewChar", SheetStyle.SHADOWDARK, standard_user, classes=_default_classes())
        assert char.name == "NewChar"
        assert char.style == SheetStyle.SHADOWDARK
        assert char.owner_id == standard_user.id
        assert isinstance(char.character_data, dict)

    @pytest.mark.asyncio
    async def test_standard_user_limit_25(self, db_session, standard_user):
        # Create 25 characters (the limit)
        for i in range(25):
            char = CharacterRecord(
                name=f"Char{i}",
                style=SheetStyle.DND5E,
                owner_id=standard_user.id,
                character_data={"name": f"Char{i}"},
            )
            db_session.add(char)
        await db_session.flush()

        # The 26th should fail
        with pytest.raises(CharacterServiceError, match="limited to 25"):
            await create_character(db_session, "TooMany", SheetStyle.DND5E, standard_user, classes=_default_classes())

    @pytest.mark.asyncio
    async def test_admin_bypasses_limit(self, db_session, admin_user):
        # Admin should never hit the limit check
        for i in range(26):
            char = CharacterRecord(
                name=f"AdminChar{i}",
                style=SheetStyle.DND5E,
                owner_id=admin_user.id,
                character_data={"name": f"AdminChar{i}"},
            )
            db_session.add(char)
        await db_session.flush()

        # 27th should still work for admin
        char = await create_character(db_session, "NoLimit", SheetStyle.A5E, admin_user, classes=_default_classes())
        assert char.name == "NoLimit"

    @pytest.mark.asyncio
    async def test_premium_bypasses_limit(self, db_session, premium_user):
        for i in range(26):
            char = CharacterRecord(
                name=f"PremChar{i}",
                style=SheetStyle.DND5E,
                owner_id=premium_user.id,
                character_data={"name": f"PremChar{i}"},
            )
            db_session.add(char)
        await db_session.flush()

        char = await create_character(db_session, "PremNoLimit", SheetStyle.A5E, premium_user, classes=_default_classes())
        assert char.name == "PremNoLimit"

    @pytest.mark.asyncio
    async def test_quota_check_acquires_row_lock(self, standard_user):
        """The quota enforcer must lock the owner's user row before counting.

        Without this, two concurrent creates both read count < 25 and both
        insert, blowing past the limit. We verify by capturing the SELECT
        that would run and checking it carries `FOR UPDATE` semantics.
        """
        from unittest.mock import AsyncMock, MagicMock
        from app.services.character_service import _assert_within_character_limit

        captured = []

        async def fake_execute(stmt, *args, **kwargs):
            captured.append(stmt)
            # Mimic scalar_one() returning 0 for the count query.
            result = MagicMock()
            result.scalar_one.return_value = 0
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=fake_execute)

        await _assert_within_character_limit(session, standard_user)

        # First statement should be the User row select with FOR UPDATE.
        assert len(captured) >= 2, "Expected a lock-select followed by a count"
        lock_stmt = captured[0]
        fu = getattr(lock_stmt, "_for_update_arg", None)
        assert fu is not None, (
            "Lock select is missing FOR UPDATE — TOCTOU race not closed"
        )

    @pytest.mark.asyncio
    async def test_quota_check_skipped_for_non_standard(self, admin_user):
        """Admin / Premium must not hit the lock path (no count, no select)."""
        from unittest.mock import AsyncMock, MagicMock
        from app.services.character_service import _assert_within_character_limit

        session = MagicMock()
        session.execute = AsyncMock()

        await _assert_within_character_limit(session, admin_user)

        session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Multiclass creation (Phase 1)
# ---------------------------------------------------------------------------

class TestCreateCharacterMulticlass:
    @pytest.mark.asyncio
    async def test_seeds_from_globalclass(self, db_session, standard_user):
        """When `classes` is provided, each entry's hit_dice / save grants /
        proficiencies are seeded from GlobalClass and aggregated."""
        from app.models.char_sheet import GlobalClass
        from app.schemas.char_sheet_specific import CharacterClassEntry

        db_session.add_all([
            GlobalClass(name="Fighter", source=SheetStyle.DND5E.value,
                        hit_dice="d10", primary_ability="STR",
                        saving_throws="Strength, Constitution",
                        proficiencies="All armor, shields, simple weapons, martial weapons"),
            GlobalClass(name="Wizard", source=SheetStyle.DND5E.value,
                        hit_dice="d6", primary_ability="INT",
                        saving_throws="Intelligence, Wisdom",
                        proficiencies="Daggers, darts, quarterstaffs"),
        ])
        await db_session.flush()

        char = await create_character(
            db_session, "Multi", SheetStyle.DND5E, standard_user,
            classes=[
                CharacterClassEntry(name="Fighter", level=3),
                CharacterClassEntry(name="Wizard", level=2),
            ],
        )
        data = char.character_data

        # Aggregate level = sum of class levels
        assert data["level"] == 5
        # Classes list persisted with seeded metadata
        assert len(data["classes"]) == 2
        fighter = next(c for c in data["classes"] if c["name"] == "Fighter")
        wizard = next(c for c in data["classes"] if c["name"] == "Wizard")
        assert fighter["hit_dice"] == "d10"
        assert fighter["hit_dice_current"] == 3 and fighter["hit_dice_max"] == 3
        assert set(fighter["saving_throw_grants"]) == {"STR", "CON"}
        assert wizard["hit_dice"] == "d6"
        assert set(wizard["saving_throw_grants"]) == {"INT", "WIS"}

        # 5e rule: only the FIRST class grants saves and weapon/armor profs.
        saves = {s["attribute"]: s["proficiency"] for s in data["saving_throws"]}
        assert saves["STR"] == 2 and saves["CON"] == 2     # Fighter (primary)
        assert saves["INT"] == 0 and saves["WIS"] == 0     # Wizard (secondary) — NOT granted
        assert saves["DEX"] == 0 and saves["CHA"] == 0

        # Fighter's weapon/armor profs seeded; Wizard's dagger/darts are NOT.
        assert "All armor" in data["proficiency"]["armor"]
        assert "Daggers" not in data["proficiency"]["weapon"]

    @pytest.mark.asyncio
    async def test_custom_class_name_without_globalclass(self, db_session, standard_user):
        """A custom class name (no matching GlobalClass row) should not crash;
        fields default to empty/provided values."""
        from app.schemas.char_sheet_specific import CharacterClassEntry

        char = await create_character(
            db_session, "Homebrew", SheetStyle.DND5E, standard_user,
            classes=[CharacterClassEntry(name="Chronomancer", level=1,
                                         hit_dice="d8",
                                         saving_throw_grants=["INT"])],
        )
        data = char.character_data
        assert data["level"] == 1
        assert data["classes"][0]["name"] == "Chronomancer"
        assert data["classes"][0]["hit_dice"] == "d8"
        # Caller-supplied save grants preserved
        int_save = next(s for s in data["saving_throws"] if s["attribute"] == "INT")
        assert int_save["proficiency"] == 2

    @pytest.mark.asyncio
    async def test_empty_classes_raises(self, db_session, standard_user):
        """Empty `classes` is rejected — callers must supply at least one entry."""
        with pytest.raises(CharacterServiceError, match="class is required"):
            await create_character(db_session, "NoClass", SheetStyle.DND5E, standard_user, classes=[])

    @pytest.mark.asyncio
    async def test_score_defaults_seeded_when_db_empty(self, db_session, standard_user):
        """No GlobalAttribute rows → fall back to the canonical six scores."""
        char = await create_character(
            db_session, "NoAttrs", SheetStyle.DND5E, standard_user,
            classes=_default_classes(),
        )
        for key in ("str_score", "dex_score", "con_score",
                    "int_score", "wis_score", "cha_score"):
            assert key in char.character_data
            assert char.character_data[key]["base"] == 10

    @pytest.mark.asyncio
    async def test_score_seeded_from_globalattribute_rows(self, db_session, standard_user):
        """Populated GlobalAttribute rows drive which score fields get defaulted."""
        from app.models.char_sheet import GlobalAttribute
        db_session.add_all([
            GlobalAttribute(name="Strength",     alias="STR", source=SheetStyle.DND5E.value),
            GlobalAttribute(name="Dexterity",    alias="DEX", source=SheetStyle.DND5E.value),
            GlobalAttribute(name="Constitution", alias="CON", source=SheetStyle.DND5E.value),
            GlobalAttribute(name="Intelligence", alias="INT", source=SheetStyle.DND5E.value),
            GlobalAttribute(name="Wisdom",       alias="WIS", source=SheetStyle.DND5E.value),
            GlobalAttribute(name="Charisma",     alias="CHA", source=SheetStyle.DND5E.value),
        ])
        await db_session.flush()

        char = await create_character(
            db_session, "SeededAttrs", SheetStyle.DND5E, standard_user,
            classes=_default_classes(),
        )
        for key in ("str_score", "dex_score", "con_score",
                    "int_score", "wis_score", "cha_score"):
            assert char.character_data[key]["base"] == 10


class TestCreateCharacterSkillSeeding:
    @pytest.mark.asyncio
    async def test_seeds_full_skill_list_for_dnd5e(self, db_session, standard_user):
        from app.models.char_sheet import GlobalSkill
        db_session.add_all([
            GlobalSkill(name="Acrobatics", attribute="DEX",
                        source=SheetStyle.DND5E.value,
                        example_uses="Stay on your feet."),
            GlobalSkill(name="Athletics", attribute="STR",
                        source=SheetStyle.DND5E.value,
                        example_uses="Climb a wall."),
        ])
        await db_session.flush()

        char = await create_character(
            db_session, "Skilled", SheetStyle.DND5E, standard_user,
            classes=_default_classes(),
        )
        skills = char.character_data["skills"]
        names = {s["name"] for s in skills}
        assert names == {"Acrobatics", "Athletics"}
        for s in skills:
            assert s["proficiency"] == 0
            assert s["misc"] == 0
            assert s["attribute"] in {"STR", "DEX", "CON", "INT", "WIS", "CHA"}

    @pytest.mark.asyncio
    async def test_shadowdark_skips_skill_seeding(self, db_session, standard_user):
        char = await create_character(
            db_session, "SDChar", SheetStyle.SHADOWDARK, standard_user,
            classes=_default_classes(),
        )
        assert char.character_data["skills"] == []

    @pytest.mark.asyncio
    async def test_full_attribute_name_normalized_to_short_code(
        self, db_session, standard_user
    ):
        from app.models.char_sheet import GlobalSkill
        db_session.add(GlobalSkill(
            name="Perception", attribute="Wisdom",
            source=SheetStyle.DND5E.value,
        ))
        await db_session.flush()

        char = await create_character(
            db_session, "Perceptive", SheetStyle.DND5E, standard_user,
            classes=_default_classes(),
        )
        perception = next(s for s in char.character_data["skills"]
                          if s["name"] == "Perception")
        assert perception["attribute"] == "WIS"


class TestCharacterSchemaMulticlass:
    def test_legacy_character_class_migrates_to_classes_list(self):
        """Loading a legacy blob with only character_class/level should
        auto-populate the classes list via the schema validator."""
        from app.schemas.char_sheet_specific import Character

        legacy = {
            "owner_id": "u1",
            "style": SheetStyle.DND5E.value,
            "name": "Olden",
            "race": {"ancestry": "Human", "culture": None, "lineage": None},
            "background": "Peasant",
            "destiny": {"name": "Survive"},
            "prof_bonus": 2,
            "ac": {"base": 10, "misc": 0},
            "initiative": {"base": 0, "misc": 0},
            "inspiration": True,
            "conditions": [],
            "speed": 30,
            "size": "Medium",
            "proficiency": {"weapon": [], "armor": [], "language": [],
                            "instrument": [], "tool": [], "game": []},
            "character_class": "Rogue",
            "level": 4,
        }
        c = Character(**legacy)
        assert len(c.classes) == 1
        assert c.classes[0].name == "Rogue"
        assert c.classes[0].level == 4
        assert c.level == 4
        assert c.character_class == "Rogue"

    def test_level_is_sum_of_class_levels(self):
        from app.schemas.char_sheet_specific import Character, CharacterClassEntry

        data = {
            "owner_id": "u1",
            "style": SheetStyle.DND5E.value,
            "name": "Multi",
            "race": {"ancestry": "Human", "culture": None, "lineage": None},
            "background": "Peasant",
            "destiny": {"name": "Survive"},
            "prof_bonus": 2,
            "ac": {"base": 10, "misc": 0},
            "initiative": {"base": 0, "misc": 0},
            "inspiration": True,
            "conditions": [],
            "speed": 30,
            "size": "Medium",
            "proficiency": {"weapon": [], "armor": [], "language": [],
                            "instrument": [], "tool": [], "game": []},
            "classes": [
                CharacterClassEntry(name="Fighter", level=3).model_dump(),
                CharacterClassEntry(name="Wizard", level=2).model_dump(),
            ],
        }
        c = Character(**data)
        assert c.level == 5
        # Multi-class summary joins entries with levels
        assert "Fighter 3" in c.character_class and "Wizard 2" in c.character_class


# ---------------------------------------------------------------------------
# delete_character
# ---------------------------------------------------------------------------

class TestDeleteCharacter:
    @pytest.mark.asyncio
    async def test_owner_can_delete(self, db_session, standard_user, sample_character):
        await delete_character(db_session, sample_character.id, standard_user)
        with pytest.raises(CharacterServiceError, match="not found"):
            await get_character(db_session, sample_character.id, standard_user)

    @pytest.mark.asyncio
    async def test_other_user_cannot_delete(self, db_session, premium_user, sample_character):
        with pytest.raises(CharacterServiceError, match="Access denied"):
            await delete_character(db_session, sample_character.id, premium_user)


# ---------------------------------------------------------------------------
# update_character
# ---------------------------------------------------------------------------

class TestApplyRest:
    """Unit tests for the pure `apply_rest` helper (no DB)."""

    def _base_char(self):
        return {
            "hp_current": 5, "hp_max": 20, "hp_temp": 3, "exhaustion": 2,
            "con_score": {"base": 14, "racial": 0, "level": 0, "misc": 0},  # +2 mod
            "classes": [
                {"name": "Fighter", "level": 3, "hit_dice": "d10",
                 "hit_dice_current": 2, "hit_dice_max": 3},
                {"name": "Wizard",  "level": 2, "hit_dice": "d6",
                 "hit_dice_current": 1, "hit_dice_max": 2},
            ],
            "magic_resources": [
                {"name": "Wizard", "magic_type": "Slots / Level",
                 "current": [2, 0], "maximum": [4, 2]},
                {"name": "Pact",   "magic_type": "Slots",
                 "current": [0],    "maximum": [2]},
            ],
            "abilities": [
                {"name": "Action Surge", "tracker": {"current": 0, "maximum": 1, "reset_on": "short"}},
                {"name": "Lucky",        "tracker": {"current": 0, "maximum": 3, "reset_on": "long"}},
                {"name": "Manual",       "tracker": {"current": 0, "maximum": 1, "reset_on": "none"}},
            ],
        }

    def test_short_rest_spends_hit_dice_and_restores_hp(self):
        out = apply_rest(self._base_char(), "short", {"hit_dice_spent": {"Fighter": 1}})
        fighter = next(c for c in out["classes"] if c["name"] == "Fighter")
        assert fighter["hit_dice_current"] == 1
        # d10 avg = 6, + CON 2 = 8 per die; started at 5, cap at 20
        assert out["hp_current"] == 13

    def test_short_rest_regains_slots_when_opted(self):
        out = apply_rest(self._base_char(), "short", {"regain_slots": True})
        pact = next(r for r in out["magic_resources"] if r["name"] == "Pact")
        wiz  = next(r for r in out["magic_resources"] if r["name"] == "Wizard")
        assert pact["current"] == [2]          # SLOTS refilled
        assert wiz["current"] == [2, 0]        # PERLEVEL untouched on short rest

    def test_short_rest_resets_short_trackers_only(self):
        out = apply_rest(self._base_char(), "short", {})
        trackers = {a["name"]: a["tracker"]["current"] for a in out["abilities"]}
        assert trackers["Action Surge"] == 1   # reset
        assert trackers["Lucky"] == 0          # long-reset, untouched
        assert trackers["Manual"] == 0         # manual, untouched

    def test_long_rest_full_hp_and_refill_slots(self):
        out = apply_rest(self._base_char(), "long", {})
        assert out["hp_current"] == 20
        assert out["hp_temp"] == 0
        assert out["exhaustion"] == 1  # 2 - 1
        # All resources refilled on long rest
        wiz  = next(r for r in out["magic_resources"] if r["name"] == "Wizard")
        pact = next(r for r in out["magic_resources"] if r["name"] == "Pact")
        assert wiz["current"] == [4, 2]
        assert pact["current"] == [2]

    def test_long_rest_regains_half_total_level_hd(self):
        out = apply_rest(self._base_char(), "long", {})
        # total_level = 5 → regain floor(5/2) = 2 HD
        fighter = next(c for c in out["classes"] if c["name"] == "Fighter")
        wizard  = next(c for c in out["classes"] if c["name"] == "Wizard")
        total_regain = (fighter["hit_dice_current"] - 2) + (wizard["hit_dice_current"] - 1)
        assert total_regain == 2
        # Respects hit_dice_max caps
        assert fighter["hit_dice_current"] <= fighter["hit_dice_max"]
        assert wizard["hit_dice_current"] <= wizard["hit_dice_max"]

    def test_long_rest_resets_both_tracker_kinds(self):
        out = apply_rest(self._base_char(), "long", {})
        trackers = {a["name"]: a["tracker"]["current"] for a in out["abilities"]}
        assert trackers["Action Surge"] == 1
        assert trackers["Lucky"] == 3
        assert trackers["Manual"] == 0  # manual still untouched

    def test_short_rest_resets_exertion(self):
        base = self._base_char()
        base["exertion_max"] = 5
        base["exertion_current"] = 1
        out = apply_rest(base, "short", {})
        assert out["exertion_current"] == 5

    def test_long_rest_resets_exertion(self):
        base = self._base_char()
        base["exertion_max"] = 5
        base["exertion_current"] = 1
        out = apply_rest(base, "long", {})
        assert out["exertion_current"] == 5

    def test_unknown_rest_kind_raises(self):
        with pytest.raises(CharacterServiceError, match="Unknown rest kind"):
            apply_rest(self._base_char(), "bogus", {})


class TestRestCharacterRBAC:
    @pytest.mark.asyncio
    async def test_owner_can_rest(self, db_session, standard_user, sample_character):
        rec = await rest_character(db_session, sample_character.id, "long", {}, standard_user)
        assert rec.character_data["hp_current"] == rec.character_data["hp_max"]

    @pytest.mark.asyncio
    async def test_other_user_cannot_rest(self, db_session, premium_user, sample_character):
        with pytest.raises(CharacterServiceError, match="Access denied"):
            await rest_character(db_session, sample_character.id, "short", {}, premium_user)


class TestUpdateCharacter:
    @pytest.mark.asyncio
    async def test_owner_can_update(self, db_session, standard_user, sample_character):
        updated = await update_character(
            db_session, sample_character.id, {"background": "Noble"}, standard_user,
        )
        assert updated.character_data["background"] == "Noble"

    @pytest.mark.asyncio
    async def test_update_syncs_name(self, db_session, standard_user, sample_character):
        updated = await update_character(
            db_session, sample_character.id, {"name": "Renamed"}, standard_user,
        )
        assert updated.name == "Renamed"
        assert updated.character_data["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_other_user_cannot_update(self, db_session, premium_user, sample_character):
        with pytest.raises(CharacterServiceError, match="Access denied"):
            await update_character(
                db_session, sample_character.id, {"name": "Hacked"}, premium_user,
            )


# ---------------------------------------------------------------------------
# Phase 3: Currency seeding + isolation
# ---------------------------------------------------------------------------

class TestCurrencyDefaults:
    @pytest.mark.asyncio
    async def test_dnd5e_seeds_five_currencies(self, db_session, standard_user):
        char = await create_character(
            db_session, "Coins5e", SheetStyle.DND5E, standard_user,
            classes=_default_classes(),
        )
        money = char.character_data["currency"]
        assert set(money.keys()) == {"CP", "SP", "EP", "GP", "PP"}
        assert all(v == 0 for v in money.values())

    @pytest.mark.asyncio
    async def test_a5e_seeds_five_currencies(self, db_session, standard_user):
        char = await create_character(
            db_session, "CoinsA5e", SheetStyle.A5E, standard_user,
            classes=_default_classes(),
        )
        money = char.character_data["currency"]
        assert set(money.keys()) == {"CP", "SP", "EP", "GP", "PP"}

    @pytest.mark.asyncio
    async def test_shadowdark_seeds_only_gp(self, db_session, standard_user):
        char = await create_character(
            db_session, "CoinsSD", SheetStyle.SHADOWDARK, standard_user,
            classes=_default_classes(),
        )
        money = char.character_data["currency"]
        assert money == {"GP": 0}

    @pytest.mark.asyncio
    async def test_money_update_does_not_leak_across_characters(
        self, db_session, standard_user
    ):
        """Updating one character's money must not touch another character."""
        a = await create_character(
            db_session, "A", SheetStyle.DND5E, standard_user, classes=_default_classes(),
        )
        b = await create_character(
            db_session, "B", SheetStyle.DND5E, standard_user, classes=_default_classes(),
        )
        new_money = {"CP": 0, "SP": 5, "EP": 0, "GP": 100, "PP": 0}
        await update_character(
            db_session, a.id, {"currency": new_money}, standard_user,
        )
        await db_session.refresh(a)
        await db_session.refresh(b)
        assert a.character_data["currency"]["GP"] == 100
        assert b.character_data["currency"]["GP"] == 0

    @pytest.mark.asyncio
    async def test_other_user_cannot_modify_money(
        self, db_session, standard_user, premium_user
    ):
        char = await create_character(
            db_session, "Locked", SheetStyle.DND5E, standard_user,
            classes=_default_classes(),
        )
        with pytest.raises(CharacterServiceError, match="Access denied"):
            await update_character(
                db_session, char.id,
                {"currency": {"GP": 9999}},
                premium_user,
            )


# ---------------------------------------------------------------------------
# Phase 1: Proficiency bonus scaling
# ---------------------------------------------------------------------------

class TestProfBonusScaling:
    def test_prof_bonus_helper_table(self):
        from app.services.character_seeding import prof_bonus_for as _prof_bonus_for
        # 5e proficiency-bonus table
        assert _prof_bonus_for(1, SheetStyle.DND5E) == 2
        assert _prof_bonus_for(4, SheetStyle.DND5E) == 2
        assert _prof_bonus_for(5, SheetStyle.DND5E) == 3
        assert _prof_bonus_for(8, SheetStyle.DND5E) == 3
        assert _prof_bonus_for(9, SheetStyle.DND5E) == 4
        assert _prof_bonus_for(13, SheetStyle.DND5E) == 5
        assert _prof_bonus_for(17, SheetStyle.DND5E) == 6
        assert _prof_bonus_for(20, SheetStyle.DND5E) == 6
        # A5e follows the same curve
        assert _prof_bonus_for(5, SheetStyle.A5E) == 3
        # Shadowdark: always 0 (unused)
        assert _prof_bonus_for(1, SheetStyle.SHADOWDARK) == 0
        assert _prof_bonus_for(10, SheetStyle.SHADOWDARK) == 0

    @pytest.mark.asyncio
    async def test_create_character_seeds_prof_from_level(self, db_session, standard_user):
        from app.schemas.char_sheet_specific import CharacterClassEntry
        char = await create_character(
            db_session, "Fighter5", SheetStyle.DND5E, standard_user,
            classes=[CharacterClassEntry(name="Fighter", level=5)],
        )
        assert char.character_data["prof_bonus"] == 3

    @pytest.mark.asyncio
    async def test_shadowdark_prof_zero(self, db_session, standard_user):
        char = await create_character(
            db_session, "ShadowKid", SheetStyle.SHADOWDARK, standard_user,
            classes=_default_classes(),
        )
        assert char.character_data["prof_bonus"] == 0

    @pytest.mark.asyncio
    async def test_update_rederives_prof_bonus_on_classes_change(
        self, db_session, standard_user, sample_character,
    ):
        # sample_character is Fighter 1 → prof 2
        assert sample_character.character_data["prof_bonus"] == 2
        updated = await update_character(
            db_session, sample_character.id,
            {"classes": [{"name": "Fighter", "level": 5}]},
            standard_user,
        )
        assert updated.character_data["prof_bonus"] == 3
        assert updated.character_data["level"] == 5

    @pytest.mark.asyncio
    async def test_update_without_classes_preserves_prof(
        self, db_session, standard_user, sample_character,
    ):
        updated = await update_character(
            db_session, sample_character.id,
            {"background": "Noble"},
            standard_user,
        )
        # prof_bonus untouched when classes isn't part of the update
        assert updated.character_data["prof_bonus"] == sample_character.character_data["prof_bonus"]


# ---------------------------------------------------------------------------
# Phase 1: Roleplaying fields round-trip through Character schema
# ---------------------------------------------------------------------------

class TestRoleplayingFieldsRoundtrip:
    @pytest.mark.asyncio
    async def test_classes_swap_reseeds_saves_and_profs(self, db_session, standard_user):
        """Changing primary class via update_character replaces saves + weapon/armor profs,
        but preserves language/tool/instrument/game entries the player added."""
        from app.models.char_sheet import GlobalClass
        from app.schemas.char_sheet_specific import CharacterClassEntry

        db_session.add_all([
            GlobalClass(name="Fighter", source=SheetStyle.DND5E.value, hit_dice="d10",
                        primary_ability="STR",
                        saving_throws="Strength, Constitution",
                        proficiencies="All armor, shields, martial weapons"),
            GlobalClass(name="Cleric", source=SheetStyle.DND5E.value, hit_dice="d8",
                        primary_ability="WIS",
                        saving_throws="Wisdom, Charisma",
                        proficiencies="Light armor, Medium armor, shields, simple weapons"),
        ])
        await db_session.flush()

        char = await create_character(
            db_session, "Switcher", SheetStyle.DND5E, standard_user,
            classes=[CharacterClassEntry(name="Fighter", level=3)],
        )
        # User adds a language (non-class-granted proficiency)
        data = dict(char.character_data)
        data["proficiency"]["language"] = ["Elvish"]
        char.character_data = data
        await db_session.flush()

        # Swap primary class to Cleric
        updated = await update_character(
            db_session, char.id,
            {"classes": [{"name": "Cleric", "level": 3}]},
            standard_user,
        )
        saves = {s["attribute"]: s["proficiency"] for s in updated.character_data["saving_throws"]}
        assert saves["WIS"] == 2 and saves["CHA"] == 2       # Cleric saves now
        assert saves["STR"] == 0 and saves["CON"] == 0       # Fighter saves gone
        assert "Light armor" in updated.character_data["proficiency"]["armor"]
        assert "All armor" not in updated.character_data["proficiency"]["armor"]
        # Language preserved through class swap
        assert updated.character_data["proficiency"]["language"] == ["Elvish"]

    @pytest.mark.asyncio
    async def test_adding_secondary_class_doesnt_add_saves(self, db_session, standard_user):
        from app.models.char_sheet import GlobalClass
        from app.schemas.char_sheet_specific import CharacterClassEntry

        db_session.add_all([
            GlobalClass(name="Fighter", source=SheetStyle.DND5E.value, hit_dice="d10",
                        primary_ability="STR",
                        saving_throws="Strength, Constitution",
                        proficiencies="All armor"),
            GlobalClass(name="Wizard", source=SheetStyle.DND5E.value, hit_dice="d6",
                        primary_ability="INT",
                        saving_throws="Intelligence, Wisdom",
                        proficiencies="Daggers"),
        ])
        await db_session.flush()

        char = await create_character(
            db_session, "MC", SheetStyle.DND5E, standard_user,
            classes=[CharacterClassEntry(name="Fighter", level=3)],
        )
        updated = await update_character(
            db_session, char.id,
            {"classes": [
                {"name": "Fighter", "level": 3},
                {"name": "Wizard",  "level": 1},
            ]},
            standard_user,
        )
        saves = {s["attribute"]: s["proficiency"] for s in updated.character_data["saving_throws"]}
        # Secondary Wizard must NOT confer saves; primary Fighter still does
        assert saves["STR"] == 2 and saves["CON"] == 2
        assert saves["INT"] == 0 and saves["WIS"] == 0
        # Level sum + prof_bonus still scale across all classes
        assert updated.character_data["level"] == 4
        assert updated.character_data["prof_bonus"] == 2  # L4 = +2

    @pytest.mark.asyncio
    async def test_roleplay_fields_persist(self, db_session, standard_user, sample_character):
        await update_character(
            db_session, sample_character.id,
            {
                "appearance": "Tall, auburn hair.",
                "personality": "Cheerful but stubborn.",
                "ideals": "Honor above all.",
                "bonds": "My late mentor's sword.",
                "flaws": "Quick to anger.",
                "backstory": "Raised in the north mountains.",
            },
            standard_user,
        )
        fresh = await get_character(db_session, sample_character.id, standard_user)
        assert fresh.character_data["appearance"] == "Tall, auburn hair."
        assert fresh.character_data["personality"] == "Cheerful but stubborn."
        assert fresh.character_data["flaws"] == "Quick to anger."


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

class TestExportImport:
    async def test_export_returns_versioned_envelope(self, db_session, standard_user, sample_character):
        data = await export_character(db_session, sample_character.id, standard_user)
        assert data["version"] == 5
        assert data["name"] == sample_character.name
        assert data["style"] == sample_character.style.value
        assert "character_data" in data
        assert "exported_at" in data

    async def test_export_denied_for_non_owner(self, db_session, admin_user, standard_user, sample_character):
        other = User(
            username="other_user",
            email="other@test.com",
            hashed_password="x",
            role=UserRole.STANDARD,
        )
        db_session.add(other)
        await db_session.flush()
        await db_session.refresh(other)
        with pytest.raises(CharacterServiceError, match="Access denied"):
            await export_character(db_session, sample_character.id, other)

    async def test_import_creates_character_with_correct_owner(self, db_session, standard_user, sample_character):
        exported = await export_character(db_session, sample_character.id, standard_user)
        rec = await import_character(
            db_session, exported["name"], SheetStyle(exported["style"]),
            exported["character_data"], standard_user,
        )
        assert rec.owner_id == standard_user.id
        assert rec.name == exported["name"]
        assert rec.id != sample_character.id

    async def test_import_overrides_owner_id(self, db_session, standard_user, admin_user, sample_character):
        exported = await export_character(db_session, sample_character.id, standard_user)
        rec = await import_character(
            db_session, exported["name"], SheetStyle(exported["style"]),
            exported["character_data"], admin_user,
        )
        assert rec.character_data["owner_id"] == str(admin_user.id)

    async def test_import_invalid_data_raises(self, db_session, standard_user):
        with pytest.raises(Exception):
            await import_character(
                db_session, "Bad", SheetStyle.DND5E,
                {"invalid": "data"},
                standard_user,
            )

    async def test_import_rejects_version_newer_than_supported(
        self, db_session, standard_user, sample_character
    ):
        exported = await export_character(db_session, sample_character.id, standard_user)
        with pytest.raises(CharacterServiceError, match="newer than supported"):
            await import_character(
                db_session, exported["name"], SheetStyle(exported["style"]),
                exported["character_data"], standard_user,
                version=999,
            )

    async def test_import_rejects_unknown_old_version(
        self, db_session, standard_user, sample_character
    ):
        exported = await export_character(db_session, sample_character.id, standard_user)
        with pytest.raises(CharacterServiceError, match="No migration available"):
            await import_character(
                db_session, exported["name"], SheetStyle(exported["style"]),
                exported["character_data"], standard_user,
                version=1,
            )

    async def test_import_runs_registered_migration(
        self, db_session, standard_user, sample_character, monkeypatch
    ):
        from app.services import character_io

        exported = await export_character(db_session, sample_character.id, standard_user)
        called = []

        def _v2_to_v3(data: dict) -> dict:
            called.append(True)
            return data

        monkeypatch.setitem(character_io._MIGRATIONS, 2, _v2_to_v3)
        rec = await import_character(
            db_session, exported["name"], SheetStyle(exported["style"]),
            exported["character_data"], standard_user,
            version=2,
        )
        assert called == [True]
        assert rec.name == exported["name"]

    async def test_v3_envelope_currency_migrates_from_equipment(
        self, db_session, standard_user, sample_character
    ):
        """A v3 export with `equipment.money` must surface as `currency`.

        Pins the v3→v4 migrator: equipment wrapper goes away, money
        moves to a flat top-level dict.
        """
        exported = await export_character(db_session, sample_character.id, standard_user)
        legacy = dict(exported["character_data"])
        # Strip the v4 currency field and re-add the v3 shape.
        legacy.pop("currency", None)
        legacy["equipment"] = {"money": {"GP": 42, "SP": 7}}

        rec = await import_character(
            db_session, exported["name"], SheetStyle(exported["style"]),
            legacy, standard_user,
            version=3,
        )
        assert rec.character_data["currency"] == {"GP": 42, "SP": 7}
        assert "equipment" not in rec.character_data


def test_export_version_lives_in_character_io():
    """Pin the public location of the export version constant.

    Consumers (UI pages, API routes, CLAUDE.md docs) must import this
    from `character_io`; bumping schema now has exactly one place to
    edit, not scattered re-exports from the core service.
    """
    from app.services import character_io
    assert isinstance(character_io.EXPORT_VERSION, int)
    assert character_io.EXPORT_VERSION >= 4
