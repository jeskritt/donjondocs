"""
AI Helper Docstring
Purpose: End-to-end Playwright browser tests covering authentication, open-redirect
protection, manually rebuilding the example character (`examples/Torak Vermil.json`)
through the NiceGUI UI, verifying all expand/collapse regions & rendered text,
testing persistence across browser reloads, and checking the Characters table
(including JSON import) and Creature Catalog.
Interactions:
- Uses fixtures from `tests/e2e/conftest.py` and Quasar helpers from
  `tests/e2e/helpers.py`.
- Run via `nox -s e2e` or `pytest tests/e2e/ -v`.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect

from tests.e2e.conftest import REPO_ROOT, sign_in
from tests.e2e.helpers import (
    active_dialog,
    click_and_wait_refresh,
    fill_field,
    icon_button,
    select_quasar_option,
    set_checkbox,
    sheet_card,
)

TORAK_EXAMPLE_JSON = REPO_ROOT / "examples" / "Torak Vermil.json"


# ---------------------------------------------------------------------------
# Test 1: Auth, Middleware Redirect, Open-Redirect Guard, Logout
# ---------------------------------------------------------------------------


def test_auth_flow_and_open_redirect_protection(
    checked_page: Page, e2e_server: dict[str, str]
) -> None:
    base = e2e_server["base_url"]

    # Unauthenticated access to a protected page redirects to /login with redirect_to.
    checked_page.goto(f"{base}/characters")
    expect(checked_page).to_have_url(re.compile(r"/login\?redirect_to=/characters"))

    # External redirect_to must be sanitized to "/" (CWE-601 open-redirect fix).
    sign_in(checked_page, e2e_server, query="?redirect_to=https://evil.example/phish")
    expect(checked_page).to_have_url(f"{base}/")
    expect(checked_page.get_by_text(f"Welcome back, {e2e_server['username']}")).to_be_visible()

    # Already-authenticated visit to /login with protocol-relative redirect_to also lands on "/".
    checked_page.goto(f"{base}/login?redirect_to=//evil.example/steal")
    expect(checked_page).to_have_url(f"{base}/")

    # Logout via the header user menu clears the cookie and returns to /login.
    icon_button(checked_page.locator("header"), "account_circle").click()
    checked_page.locator(".q-menu .q-item", has_text="Logout").click()
    expect(checked_page).to_have_url(re.compile(r"/login"))


# ---------------------------------------------------------------------------
# Test 2: Manually Rebuild Torak Vermil & Verify Every Sheet Interaction
# ---------------------------------------------------------------------------


def _create_torak_via_sheet_creator(page: Page, base_url: str) -> str:
    page.goto(f"{base_url}/sheet/new")
    expect(page.get_by_text("Select Game System")).to_be_visible()

    # Pick Level Up: Advanced 5e.
    page.locator(".q-card", has_text="Level Up: Advanced 5e").first.click()
    dlg = active_dialog(page)
    expect(dlg.get_by_text("New LEVEL UP: ADVANCED 5E Character")).to_be_visible()

    fill_field(dlg, "Name", "Torak Vermil")
    fill_field(dlg, "Ancestry / Race", "Unliving/Vampire")
    fill_field(dlg, "Culture / Subrace", "Blightlander")
    fill_field(dlg, "Background", "Monster Slayer")
    select_quasar_option(page, dlg, "Class", "Fighter")
    fill_field(dlg, "Archetype", "Eldritch Knight")
    fill_field(dlg, "Level", "5")
    dlg.get_by_role("button", name="Create").click()

    expect(page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(page.get_by_text("Torak Vermil").first).to_be_visible()
    expect(page.get_by_text("Lvl 5 Fighter (Eldritch Knight)")).to_be_visible()
    return page.url


def _customize_abilities_and_saves(page: Page) -> None:
    card = sheet_card(page, "Abilities & Saves")
    icon_button(card, "edit").click()

    # Torak's ability scores: STR 15+1=16, DEX 12, CON 13, INT 12, WIS 12+1=13, CHA 14.
    scores = {
        "STR": ("15", "1"),
        "DEX": ("12", "0"),
        "CON": ("13", "0"),
        "INT": ("12", "0"),
        "WIS": ("12", "1"),
        "CHA": ("14", "0"),
    }
    # Each attribute has a label followed by a row containing Base, Race, ASI, Misc.
    base_inputs = card.locator("label.q-field").filter(
        has=page.locator(".q-field__label", has_text=re.compile(r"^Base$"))
    )
    race_inputs = card.locator("label.q-field").filter(
        has=page.locator(".q-field__label", has_text=re.compile(r"^Race$"))
    )
    for idx, (_attr, (base_v, race_v)) in enumerate(scores.items()):
        base_inputs.nth(idx).locator("input").fill(base_v)
        race_inputs.nth(idx).locator("input").fill(race_v)

    card.get_by_role("button", name="Save").click()

    # Verify computed totals & modifiers render (STR 16 / +3 / Save +6; CHA 14 / +2).
    str_row = card.locator("div.row").filter(
        has=page.locator("div", has_text=re.compile(r"^STR$"))
    ).first
    expect(str_row).to_contain_text("16")
    expect(str_row).to_contain_text("+3")
    expect(str_row).to_contain_text("+6")

    cha_row = card.locator("div.row").filter(
        has=page.locator("div", has_text=re.compile(r"^CHA$"))
    ).first
    expect(cha_row).to_contain_text("14")
    expect(cha_row).to_contain_text("+2")


def _customize_skills(page: Page) -> None:
    card = sheet_card(page, "Skills")
    icon_button(card, "edit").click()

    # Arcana: cycle proficiency 0 -> 1 -> 2 (Proficient ●) and add note "Monstrosities".
    # Filter by `.cursor-pointer` so we match the visible edit block, not the hidden display row.
    arcana_block = (
        card.locator(".border-b")
        .filter(has=page.locator("div", has_text=re.compile(r"^Arcana$")))
        .filter(has=page.locator(".cursor-pointer"))
        .first
    )
    arcana_badge = arcana_block.locator(".cursor-pointer").first
    arcana_badge.click()
    arcana_badge.click()
    expect(arcana_badge).to_have_text("●")
    fill_field(arcana_block, "Notes", "Monstrosities")

    # Athletics: cycle proficiency 0 -> 1 -> 2 (Proficient ●).
    athletics_block = (
        card.locator(".border-b")
        .filter(has=page.locator("div", has_text=re.compile(r"^Athletics$")))
        .filter(has=page.locator(".cursor-pointer"))
        .first
    )
    ath_badge = athletics_block.locator(".cursor-pointer").first
    ath_badge.click()
    ath_badge.click()
    expect(ath_badge).to_have_text("●")

    card.get_by_role("button", name="Save").click()

    # Verify rendered skill note and computed bonuses (Arcana INT+1 + PROF+3 = +4; Athletics STR+3 + PROF+3 = +6).
    expect(card.get_by_text("Monstrosities")).to_be_visible()
    arcana_display = card.locator(".border-b").filter(
        has=page.locator("div", has_text=re.compile(r"^Arcana$"))
    ).first
    expect(arcana_display).to_contain_text("+4")
    athletics_display = card.locator(".border-b").filter(
        has=page.locator("div", has_text=re.compile(r"^Athletics$"))
    ).first
    expect(athletics_display).to_contain_text("+6")


def _customize_hp_defenses_proficiencies_description(page: Page) -> None:
    # --- Hit Points ---
    hp_card = sheet_card(page, "Hit Points")
    icon_button(hp_card, "edit").click()
    fill_field(hp_card, "Current HP", "39")
    fill_field(hp_card, "Max HP", "39")
    hp_card.get_by_role("button", name="Save").click()
    expect(hp_card.get_by_text("39 / 39")).to_be_visible()
    expect(page.get_by_text("39/39")).to_be_visible()

    # Inline +/- adjuster on Current HP and Strife.
    hp_row = hp_card.locator(".border-b", has_text="Current / Max").first
    icon_button(hp_row, "remove").click()
    expect(hp_card.get_by_text("38 / 39")).to_be_visible()
    expect(page.get_by_text("38/39")).to_be_visible()
    icon_button(hp_row, "add").click()
    expect(hp_card.get_by_text("39 / 39")).to_be_visible()

    strife_row = hp_card.locator(".border-b", has_text="Strife").first
    icon_button(strife_row, "add").click()
    expect(strife_row).to_contain_text("1 / 6")
    icon_button(strife_row, "remove").click()
    expect(strife_row).to_contain_text("0 / 6")

    # --- Defenses & Inspiration ---
    def_card = sheet_card(page, "Defenses")
    icon_button(def_card, "edit").click()
    fill_field(def_card, "Resistances", "Poison, Adv on Poison saves")
    fill_field(def_card, "Immunities", "Disease, Necrotic")
    fill_field(def_card, "Vulnerabilities", "Radiant")
    def_card.get_by_role("button", name="Save").click()
    expect(def_card.get_by_text("Poison, Adv on Poison saves")).to_be_visible()
    expect(def_card.get_by_text("Disease, Necrotic")).to_be_visible()
    expect(def_card.get_by_text("Radiant")).to_be_visible()

    # A5e characters seed with Inspiration=True; toggle it off then back on.
    insp_checkbox = def_card.locator(".border-b", has_text="Inspiration").first.locator(".q-checkbox").first
    expect(insp_checkbox).to_have_attribute("aria-checked", "true")
    click_and_wait_refresh(page, insp_checkbox)
    expect(insp_checkbox).to_have_attribute("aria-checked", "false")
    click_and_wait_refresh(page, insp_checkbox)
    expect(insp_checkbox).to_have_attribute("aria-checked", "true")

    # --- Proficiencies ---
    prof_card = sheet_card(page, "Proficiencies")
    icon_button(prof_card, "edit").click()
    fill_field(prof_card, "Languages", "Common, Sylvan, Dwarven")
    fill_field(prof_card, "Tools", "Alchemist's Supplies")
    prof_card.get_by_role("button", name="Save").click()
    expect(prof_card.get_by_text("Common, Sylvan, Dwarven")).to_be_visible()
    expect(prof_card.get_by_text("Alchemist's Supplies")).to_be_visible()

    # --- Description & Destiny ---
    desc_card = sheet_card(page, "Description")
    icon_button(desc_card, "edit").click()
    fill_field(desc_card, "Destiny", "Victory")
    fill_field(desc_card, "Source of Inspiration", "Defeat worthy foe")
    fill_field(desc_card, "Inspiration Feat", "1 hour, expertise on opposed rolls")
    fill_field(desc_card, "Title", "Undying Scion, Winter's Heart")
    fill_field(desc_card, "Gender", "Male")
    fill_field(desc_card, "Eyes", "Red")
    fill_field(desc_card, "Hair", "White")
    fill_field(desc_card, "Skin", "Pale")
    desc_card.get_by_role("button", name="Save").click()
    expect(desc_card.get_by_text("Victory")).to_be_visible()
    expect(desc_card.get_by_text("Defeat worthy foe")).to_be_visible()
    expect(desc_card.get_by_text("Undying Scion, Winter's Heart")).to_be_visible()


def _customize_actions(page: Page) -> None:
    card = sheet_card(page, "Actions")

    card.get_by_role("button", name="Add Action").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Fanged Bite")
    select_quasar_option(page, dlg, "Attribute", "STR")
    set_checkbox(dlg, "Proficient", True)
    fill_field(dlg, "Damage (e.g. 1d8 slashing)", "1d6 + 3 P")
    fill_field(dlg, "Range (e.g. 5 ft or 20/60)", "5 ft")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    card.get_by_role("button", name="Add Action").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Longsword")
    select_quasar_option(page, dlg, "Attribute", "STR")
    set_checkbox(dlg, "Proficient", True)
    fill_field(dlg, "Damage (e.g. 1d8 slashing)", "1D8 + 4 S")
    fill_field(dlg, "Attack misc", "1")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    bite_row = card.locator(".border-b", has_text="Fanged Bite").first
    expect(bite_row).to_contain_text("+6")
    expect(bite_row).to_contain_text("1d6 + 3 P • 5 ft")

    sword_row = card.locator(".border-b", has_text="Longsword").first
    expect(sword_row).to_contain_text("+7")
    expect(sword_row).to_contain_text("1D8 + 4 S")


def _customize_abilities_and_verify_expand_collapse(page: Page) -> None:
    card = sheet_card(page, "Abilities, Magic & Features")

    # Add Heritage ability with a 4-use long-rest tracker.
    card.get_by_role("button", name="Add Ability / Feature").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Blood Feasting")
    select_quasar_option(page, dlg, "Source", "Heritage")
    fill_field(
        dlg,
        "Description",
        "On a short rest I can drink the blood from a corpse and regain hit dice.",
    )
    set_checkbox(dlg, "Track uses", True)
    fill_field(dlg, "Max uses", "4")
    select_quasar_option(page, dlg, "Reset on", "long")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Add Class ability with a 1-use short-rest tracker to test multi-source tabs.
    card.get_by_role("button", name="Add Ability / Feature").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Fighting Style: Battle Ready")
    select_quasar_option(page, dlg, "Source", "Class")
    fill_field(
        dlg,
        "Description",
        "Activate 2 stances in a single Bonus Action without spending exertion.",
    )
    set_checkbox(dlg, "Track uses", True)
    fill_field(dlg, "Max uses", "1")
    select_quasar_option(page, dlg, "Reset on", "short")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Heritage tab is active; expand Blood Feasting and verify description + tracker.
    bf_exp = card.locator(".q-expansion-item", has_text="Blood Feasting").first
    bf_header = bf_exp.locator(".q-expansion-item__container > .q-item").first
    bf_content = bf_exp.locator(".q-expansion-item__content").first
    expect(bf_content).to_be_hidden()

    bf_header.click()
    expect(bf_content).to_be_visible()
    expect(bf_content).to_contain_text("drink the blood from a corpse")
    expect(bf_content).to_contain_text("Uses (4/4, resets long)")

    # Ticking a use checkbox must persist AND keep the expansion open across _save.
    bf_content.locator(".q-checkbox").first.click()
    expect(bf_content).to_be_visible()
    expect(bf_content).to_contain_text("Uses (3/4, resets long)")

    # Collapse -> hidden, then switch to Class source tab and expand Battle Ready.
    bf_header.click()
    expect(bf_content).to_be_hidden()

    card.get_by_role("tab", name="Class", exact=True).click()
    br_exp = card.locator(".q-expansion-item", has_text="Fighting Style: Battle Ready").first
    br_exp.locator(".q-expansion-item__container > .q-item").first.click()
    br_content = br_exp.locator(".q-expansion-item__content").first
    expect(br_content).to_be_visible()
    expect(br_content).to_contain_text("Activate 2 stances in a single Bonus Action")
    expect(br_content).to_contain_text("Uses (1/1, resets short)")


def _customize_magic_and_verify_expand_collapse(page: Page) -> None:
    card = sheet_card(page, "Abilities, Magic & Features")
    card.get_by_role("tab", name="Magic", exact=True).click()

    # Add Magic Resource: Spellcasting (Eldritch Knight) — CHA, Slots/Level [3].
    card.get_by_role("button", name="Add Magic Resource").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Spellcasting (Eldritch Knight)")
    fill_field(dlg, "Source (class/feat/item)", "Class")
    select_quasar_option(page, dlg, "Magic Type", "Slots / Level")
    select_quasar_option(page, dlg, "Attribute", "CHA")
    fill_field(dlg, "Slots (comma-separated, e.g. 4,2)", "3")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Add Magic Resource: Darkwood Magic — CHA, Slots/Level [1, 1].
    card.get_by_role("button", name="Add Magic Resource").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Darkwood Magic")
    fill_field(dlg, "Source (class/feat/item)", "Blightlander")
    select_quasar_option(page, dlg, "Magic Type", "Slots / Level")
    select_quasar_option(page, dlg, "Attribute", "CHA")
    fill_field(dlg, "Slots (comma-separated, e.g. 4,2)", "1, 1")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Expand Spellcasting resource and verify CHA Attack (+5 = +2 CHA +3 PROF) & Save DC (13).
    ek_exp = card.locator(".q-expansion-item", has_text="Spellcasting (Eldritch Knight)").first
    ek_exp.locator(".q-expansion-item__container > .q-item").first.click()
    ek_content = ek_exp.locator(".q-expansion-item__content").first
    expect(ek_content).to_be_visible()
    expect(ek_content).to_contain_text("Attribute: CHA")
    expect(ek_content).to_contain_text("Attack: +5")
    expect(ek_content).to_contain_text("Save DC: 13")

    # Spend a slot checkbox -> stays expanded -> Reset restores all unchecked.
    click_and_wait_refresh(page, ek_content.locator(".q-checkbox").first)
    expect(ek_content).to_be_visible()
    expect(ek_content.locator(".q-checkbox").first).to_have_attribute("aria-checked", "true")
    click_and_wait_refresh(page, ek_content.get_by_role("button", name="Reset"))
    expect(ek_content.locator(".q-checkbox").first).to_have_attribute("aria-checked", "false")

    # Add Cantrip: Hoarfrost.
    card.get_by_role("button", name="Add Spell").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Hoarfrost")
    fill_field(dlg, "Level (0=cantrip)", "0")
    fill_field(dlg, "Description", "A melee weapon you are holding is imbued with cold for **1d4 cold damage**.")
    fill_field(dlg, "Casting Time", "1 BA")
    fill_field(dlg, "Range", "Self")
    fill_field(dlg, "Duration", "1 min or hit")
    select_quasar_option(page, dlg, "Resource", "Spellcasting (Eldritch Knight)")
    set_checkbox(dlg, "Prepared", True)
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Add 1st-level Concentration spell: Fog Cloud.
    card.get_by_role("button", name="Add Spell").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Fog Cloud")
    fill_field(dlg, "Level (0=cantrip)", "1")
    fill_field(dlg, "Description", "You create a heavily obscured area of fog.")
    fill_field(dlg, "Casting Time", "1 A")
    fill_field(dlg, "Range", "120 ft")
    fill_field(dlg, "Duration", "1 hour")
    set_checkbox(dlg, "Concentration", True)
    select_quasar_option(page, dlg, "Resource", "Darkwood Magic")
    set_checkbox(dlg, "Prepared", True)
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Click Hoarfrost row to expand -> verify extended metadata + markdown -> click again to collapse.
    hoarfrost_desc = card.get_by_text("A melee weapon you are holding is imbued with cold")
    expect(hoarfrost_desc).to_be_hidden()
    card.locator(".cursor-pointer", has_text="Hoarfrost").first.click()
    expect(hoarfrost_desc).to_be_visible()
    expect(card.get_by_text("Cantrip")).to_be_visible()
    card.locator(".cursor-pointer", has_text="Hoarfrost").first.click()
    expect(hoarfrost_desc).to_be_hidden()

    # Verify Concentration filter hides Hoarfrost and shows Fog Cloud, then clear filter.
    set_checkbox(card, "Concentration", True)
    expect(card.locator(".cursor-pointer", has_text="Fog Cloud")).to_be_visible()
    expect(card.locator(".cursor-pointer", has_text="Hoarfrost")).to_have_count(0)
    set_checkbox(card, "Concentration", False)
    expect(card.locator(".cursor-pointer", has_text="Hoarfrost")).to_be_visible()


def _customize_maneuvers_and_verify_expand_collapse(page: Page) -> None:
    card = sheet_card(page, "Abilities, Magic & Features")
    card.get_by_role("tab", name="Combat Maneuvers", exact=True).click()
    panel = card.locator(".q-tab-panel", has_text="Exertion:").first
    expect(panel).to_be_visible()

    # Edit maneuver header settings.
    icon_button(panel, "edit").first.click()
    dlg = active_dialog(page)
    expect(dlg.get_by_text("Edit Combat Maneuver Settings")).to_be_visible()
    fill_field(dlg, "Known Traditions (comma-separated)", "Arcane Knight, Cutting Omens")
    fill_field(dlg, "Exertion Current", "7")
    fill_field(dlg, "Exertion Max", "7")
    fill_field(dlg, "Maneuvers Known", "5")
    fill_field(dlg, "Max Degree", "2")
    dlg.get_by_role("button", name="Save").click()
    expect(dlg).to_be_hidden()

    expect(panel.get_by_text("Traditions: Arcane Knight, Cutting Omens")).to_be_visible()
    expect(panel.get_by_text("Exertion: 7 / 7")).to_be_visible()

    # Exertion +/- inline adjusters.
    icon_button(panel, "remove").first.click()
    expect(panel.get_by_text("Exertion: 6 / 7")).to_be_visible()
    icon_button(panel, "add").first.click()
    expect(panel.get_by_text("Exertion: 7 / 7")).to_be_visible()

    # Add Maneuver 1: Fridgid Strike (+2 Dmg).
    card.get_by_role("button", name="Add Combat Maneuver").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Fridgid Strike (+2 Dmg)")
    fill_field(dlg, "Degree", "1")
    select_quasar_option(page, dlg, "Tradition", "Arcane Knight")
    fill_field(dlg, "Exertion Cost", "1")
    select_quasar_option(page, dlg, "Action Type", "A")
    fill_field(dlg, "Description", "Make an attack; if damage is dealt reduce speed by 15 ft.")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Add Maneuver 2 (Stance): Martial Caster Stance.
    card.get_by_role("button", name="Add Combat Maneuver").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Martial Caster Stance")
    fill_field(dlg, "Degree", "1")
    select_quasar_option(page, dlg, "Tradition", "Cutting Omens")
    fill_field(dlg, "Exertion Cost", "1")
    select_quasar_option(page, dlg, "Action Type", "BA")
    set_checkbox(dlg, "Stance", True)
    fill_field(dlg, "Description", "Expertise on concentration checks; cast BA and R spell same turn.")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Expand and collapse Martial Caster Stance row.
    stance_detail = panel.locator(".pl-8", has_text="Expertise on concentration checks").first
    expect(stance_detail).to_be_hidden()
    panel.locator(".cursor-pointer", has_text="Martial Caster Stance").first.click()
    expect(stance_detail).to_be_visible()
    expect(stance_detail).to_contain_text("Stance:")
    expect(stance_detail).to_contain_text("Yes")
    panel.locator(".cursor-pointer", has_text="Martial Caster Stance").first.click()
    expect(stance_detail).to_be_hidden()


def _customize_equipment_and_verify_ac_and_expand_collapse(page: Page) -> None:
    card = sheet_card(page, "Equipment")

    # --- Currency tab ---
    card.get_by_role("tab", name="Currency", exact=True).click()
    gp_box = card.locator(".border").filter(
        has=page.locator("div", has_text=re.compile(r"^GP$"))
    ).first
    gp_inp = gp_box.locator("input").first
    gp_handle = gp_inp.element_handle()
    gp_inp.fill("115")
    page.wait_for_function("el => !el.isConnected", arg=gp_handle)
    expect(
        card.locator(".border")
        .filter(has=page.locator("div", has_text=re.compile(r"^GP$")))
        .first.locator("input")
        .first
    ).to_have_value("115")

    # --- Weapons tab (Add Custom + Equip + Expand/Collapse) ---
    card.get_by_role("tab", name="Weapons", exact=True).click()
    w_panel = card.locator(".q-tab-panel", has_text="No weapons carried.").first
    expect(w_panel).to_be_visible()
    w_panel.get_by_role("button", name="Add Custom").click()
    dlg = active_dialog(page)
    expect(dlg.get_by_text("Add Custom Weapon")).to_be_visible()
    fill_field(dlg, "Name*", "Longsword + 1")
    fill_field(dlg, "Damage (e.g. 1d8)", "1d8")
    fill_field(dlg, "Damage Type (e.g. slashing)", "slashing")
    fill_field(dlg, "Weight", "3 lbs.")
    fill_field(dlg, "Cost", "20 gp")
    fill_field(dlg, "Properties", "Defensive (medium), magic")
    fill_field(
        dlg,
        "Description (markdown)",
        "Killing a creature grants Strength modifier + proficiency temp hit points.",
    )
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    weapon_row = card.locator(".border-b", has_text="Longsword + 1").first
    click_and_wait_refresh(page, weapon_row.locator(".q-checkbox").first)  # Equip
    weapon_desc = card.get_by_text("Killing a creature grants Strength modifier")
    expect(weapon_desc).to_be_hidden()
    card.locator(".cursor-pointer", has_text="Longsword + 1").first.click()
    expect(weapon_desc).to_be_visible()
    card.locator(".cursor-pointer", has_text="Longsword + 1").first.click()
    expect(weapon_desc).to_be_hidden()

    # --- Armor tab (Add from Library: Half plate + Medium Shield -> AC = 18) ---
    card.get_by_role("tab", name="Armor", exact=True).click()
    expect(card.get_by_text("No armor carried.")).to_be_visible()
    for armor_name in ("Half plate (steel)", "Medium Shield"):
        a_panel = card.locator(".q-tab-panel").last
        a_panel.get_by_role("button", name="Add from Library").click()
        dlg = active_dialog(page)
        expect(dlg.get_by_text("Add Armor from Library")).to_be_visible()
        select_quasar_option(page, dlg, "Choose armor", armor_name, filterable=True)
        dlg.get_by_role("button", name="Add").click()
        expect(dlg).to_be_hidden()

    for armor_name in ("Half plate (steel)", "Medium Shield"):
        row = card.locator(".border-b", has_text=armor_name).first
        click_and_wait_refresh(page, row.locator(".q-checkbox").first)  # Equip

    # DEX 12 (+1), Half plate base 15 (dex_cap 2), Medium Shield +2 => AC 18.
    def_card = sheet_card(page, "Defenses")
    expect(def_card.get_by_text("15 base + 1 DEX + 2 shield")).to_be_visible()
    ac_row = def_card.locator(".border-b", has_text=re.compile(r"^AC")).first
    expect(ac_row).to_contain_text("18")

    # Expand/collapse Half plate (steel) row.
    armor_props = card.get_by_text("Low-maintenance (expertise die)")
    expect(armor_props).to_be_hidden()
    card.locator(".cursor-pointer", has_text="Half plate (steel)").first.click()
    expect(armor_props).to_be_visible()
    card.locator(".cursor-pointer", has_text="Half plate (steel)").first.click()
    expect(armor_props).to_be_hidden()

    # --- Items tab (Add Custom with Markdown Table + Attunement + Expand/Collapse) ---
    card.get_by_role("tab", name="Items", exact=True).click()
    i_panel = card.locator(".q-tab-panel", has_text="No equipment carried.").first
    expect(i_panel).to_be_visible()
    i_panel.get_by_role("button", name="Add Custom").click()
    dlg = active_dialog(page)
    expect(dlg.get_by_text("Add Custom Item")).to_be_visible()
    fill_field(dlg, "Name*", "Potion of Hill Giant Strength")
    fill_field(dlg, "Cost", "300 gp")
    fill_field(
        dlg,
        "Description (markdown)",
        "**Crafting Components:** Giant body part\n\n"
        "| Giant | Strength Score |\n|---|---|\n| Hill giant | 20 |",
    )
    set_checkbox(dlg, "Attuned", True)
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    expect(card.get_by_text("Attuned 1 / 3")).to_be_visible()

    potion_cell = card.locator("table td", has_text="Hill giant").first
    expect(potion_cell).to_be_hidden()
    card.locator(".cursor-pointer", has_text="Potion of Hill Giant Strength").first.click()
    expect(potion_cell).to_be_visible()
    expect(card.get_by_text("Crafting Components:")).to_be_visible()
    card.locator(".cursor-pointer", has_text="Potion of Hill Giant Strength").first.click()
    expect(potion_cell).to_be_hidden()


def _customize_allies_notes_and_phb_toggle(page: Page) -> None:
    # --- Allies & Stat Blocks tab ---
    page.get_by_role("tab", name="Allies & Stat Blocks", exact=True).click()
    page.get_by_role("button", name="Add Ally").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Freki")
    select_quasar_option(page, dlg, "Type", "Pet", filterable=True)
    # Selecting Pet auto-seeds the monster stat block template.
    body_field = dlg.locator("label.q-field").filter(
        has=page.locator(".q-field__label", has_text=re.compile(r"^Body$"))
    ).first.locator("textarea")
    expect(body_field).not_to_have_value("")

    body_field.fill(
        "> ## Mastif Companion\n"
        "> *Heroic Medium Beast*\n"
        "> ___ \n"
        "> ### Traits\n"
        "> ***Keen Hearing and Smell.*** Advantage on Perception checks."
    )
    dlg.get_by_role("button", name="Save").click()
    expect(dlg).to_be_hidden()

    # Expand Freki and check rendered markdown.
    freki_card = page.locator(".q-card", has_text="Freki").first
    freki_card.locator(".cursor-pointer", has_text="Freki").first.click()
    expect(freki_card.get_by_text("Mastif Companion")).to_be_visible()
    expect(freki_card.get_by_text("Keen Hearing and Smell.")).to_be_visible()

    # Toggle PHB style switch ON -> .phb class applied to markdown; toggle OFF -> removed.
    phb_switch = page.locator(".q-toggle", has_text="PHB style").first
    phb_switch.click()
    expect(freki_card.locator(".phb")).to_be_visible()
    phb_switch.click()
    expect(freki_card.locator(".phb")).to_have_count(0)

    # Collapse Freki.
    freki_card.locator(".cursor-pointer", has_text="Freki").first.click()
    expect(freki_card.get_by_text("Keen Hearing and Smell.")).to_have_count(0)

    # --- Notes tab ---
    page.get_by_role("tab", name="Notes", exact=True).click()
    page.get_by_role("button", name="Add Note").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Title", "Back Story")
    fill_field(
        dlg,
        "Body",
        "## The Widow's Nail\n\nThe fortress your family controlled along the wall.",
    )
    dlg.get_by_role("button", name="Save").click()
    expect(dlg).to_be_hidden()

    note_card = page.locator(".q-card", has_text="Back Story").first
    note_card.locator(".cursor-pointer", has_text="Back Story").first.click()
    expect(note_card.get_by_text("The Widow's Nail")).to_be_visible()
    expect(note_card.get_by_text("fortress your family controlled")).to_be_visible()
    note_card.locator(".cursor-pointer", has_text="Back Story").first.click()
    expect(note_card.get_by_text("The Widow's Nail")).to_have_count(0)


def _verify_long_rest_and_reload_persistence(page: Page) -> None:
    page.get_by_role("tab", name="Character", exact=True).click()

    # Drop HP from 39 to 38, then trigger Long Rest -> restores HP 39/39 & Blood Feasting 4/4.
    hp_card = sheet_card(page, "Hit Points")
    hp_row = hp_card.locator(".border-b", has_text="Current / Max").first
    icon_button(hp_row, "remove").click()
    expect(hp_card.get_by_text("38 / 39")).to_be_visible()

    page.get_by_role("button", name="Long Rest").click()
    dlg = active_dialog(page)
    dlg.get_by_role("button", name="Confirm").click()
    expect(dlg).to_be_hidden()
    expect(hp_card.get_by_text("39 / 39")).to_be_visible()

    # Full browser reload verifies DB persistence across every card & tab.
    page.reload()
    expect(page.get_by_text("Torak Vermil").first).to_be_visible()
    expect(page.get_by_text("39/39")).to_be_visible()
    expect(sheet_card(page, "Defenses").get_by_text("15 base + 1 DEX + 2 shield")).to_be_visible()
    expect(sheet_card(page, "Equipment").get_by_text("Attuned 1 / 3")).to_be_visible()

    # Check Blood Feasting tracker was reset to 4/4 by Long Rest.
    feat_card = sheet_card(page, "Abilities, Magic & Features")
    bf_exp = feat_card.locator(".q-expansion-item", has_text="Blood Feasting").first
    bf_exp.locator(".q-expansion-item__container > .q-item").first.click()
    expect(bf_exp.locator(".q-expansion-item__content")).to_contain_text("Uses (4/4, resets long)")

    # Allies & Notes survive reload.
    page.get_by_role("tab", name="Allies & Stat Blocks", exact=True).click()
    expect(page.locator(".q-card", has_text="Freki")).to_be_visible()
    page.get_by_role("tab", name="Notes", exact=True).click()
    expect(page.locator(".q-card", has_text="Back Story")).to_be_visible()


def test_rebuild_torak_vermil_and_verify_all_interactions(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """Manually rebuild Torak Vermil end-to-end through the browser UI."""
    _create_torak_via_sheet_creator(authed_page, e2e_server["base_url"])
    _customize_abilities_and_saves(authed_page)
    _customize_skills(authed_page)
    _customize_hp_defenses_proficiencies_description(authed_page)
    _customize_actions(authed_page)
    _customize_abilities_and_verify_expand_collapse(authed_page)
    _customize_magic_and_verify_expand_collapse(authed_page)
    _customize_maneuvers_and_verify_expand_collapse(authed_page)
    _customize_equipment_and_verify_ac_and_expand_collapse(authed_page)
    _customize_allies_notes_and_phb_toggle(authed_page)
    _verify_long_rest_and_reload_persistence(authed_page)


# ---------------------------------------------------------------------------
# Test 3: Characters Table + JSON Import Upload + Creature Catalog
# ---------------------------------------------------------------------------


def test_characters_table_import_and_creatures_catalog(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    base = e2e_server["base_url"]

    # 1. Characters page: import the bundled examples/Torak Vermil.json via ui.upload.
    authed_page.goto(f"{base}/characters")
    expect(authed_page.get_by_text("My Characters").first).to_be_visible()

    authed_page.get_by_role("button", name="Import").click()
    dlg = active_dialog(authed_page)
    expect(dlg.get_by_text("Import Character")).to_be_visible()
    dlg.locator("input[type='file']").set_input_files(str(TORAK_EXAMPLE_JSON))
    expect(dlg).to_be_hidden()

    # Table row renders with Torak Vermil and opens the sheet on row click.
    table = authed_page.locator(".q-table")
    expect(table.get_by_text("Torak Vermil").first).to_be_visible()
    table.locator("tbody tr", has_text="Torak Vermil").first.click()
    expect(authed_page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(authed_page.get_by_text("Torak Vermil").first).to_be_visible()

    # 2. Creature Catalog: create, expand/collapse stat block, search filter, delete.
    authed_page.goto(f"{base}/creatures")
    expect(authed_page.get_by_text("Creature Catalog").first).to_be_visible()

    authed_page.get_by_role("button", name="New Creature").click()
    dlg = active_dialog(authed_page)
    fill_field(dlg, "Name*", "Frost Owlbear")
    fill_field(dlg, "Challenge Rating", "3")
    fill_field(
        dlg,
        "Body (Markdown)",
        "> ## Frost Owlbear\n> *Large Monstrosity*\n> ___\n> ***Keen Sight.*** Advantage on Perception.",
    )
    dlg.get_by_role("button", name="Save").click()
    expect(dlg).to_be_hidden()

    creature_card = authed_page.locator(".q-card", has_text="Frost Owlbear").first
    expect(creature_card).to_be_visible()

    # Expand and verify PHB markdown renders; collapse again.
    creature_card.locator(".cursor-pointer", has_text="Frost Owlbear").first.click()
    expect(creature_card.get_by_text("Keen Sight.")).to_be_visible()
    creature_card.locator(".cursor-pointer", has_text="Frost Owlbear").first.click()
    expect(creature_card.get_by_text("Keen Sight.")).to_have_count(0)

    # Search filter narrows and clears cleanly (clearing after empty state also
    # guarantees the 300ms Quasar debounce finishes before we click Delete).
    search_inp = authed_page.get_by_placeholder("Search name…")
    search_inp.fill("Frost")
    expect(authed_page.locator(".q-card", has_text="Frost Owlbear").first).to_be_visible()
    search_inp.fill("NonexistentBeast")
    expect(authed_page.get_by_text("No creatures yet")).to_be_visible()
    search_inp.fill("")
    expect(authed_page.locator(".q-card", has_text="Frost Owlbear").first).to_be_visible()

    # Delete creature via confirmation dialog.
    icon_button(authed_page.locator(".q-card", has_text="Frost Owlbear").first, "delete").click()
    del_dlg = active_dialog(authed_page)
    del_dlg.get_by_role("button", name="Delete").click()
    expect(del_dlg).to_be_hidden()
    expect(authed_page.locator(".q-card", has_text="Frost Owlbear")).to_have_count(0)
