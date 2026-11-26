"""Playwright E2E tests for both D&D 5e (2024 / SRD 5.2) and D&D 5e (2014 / SRD 5.1)
using the unified Dungeons & Dragons 5e card and edition picker on /sheet/new."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import (
    active_dialog,
    fill_field,
    icon_button,
    select_quasar_option,
    sheet_card,
)


def test_dnd_2024_edition_flow_weapon_mastery_gear_mounts_and_spells(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """Create a D&D 5e (2024 / SRD 5.2) Fighter via the edition picker and verify:
    1. Unified D&D 5e card opens with '2024 Rules (SRD 5.2)' selected and 'Species' label.
    2. Weapon Mastery counter ('Masteries 0 / 3'), 'Ma' column, Mastery badge in Properties,
       expanded Mastery rule text, checkbox toggle -> 'Masteries 1 / 3', and limit edit -> '1 / 4'.
    3. 2024 Tool ('Alchemist's Supplies' Utilize/Craft inline Markdown) and Vehicle ('Airship')
       Allies stat-block seeding + 1-click Stat Block jump.
    4. 2024 Spell Library picker ('Chill Touch' Necromancy Cantrip).
    5. Persistence across full page reload and '/characters' style badge.
    """
    base = e2e_server["base_url"]
    authed_page.goto(f"{base}/sheet/new")
    expect(authed_page.get_by_text("Select Game System")).to_be_visible()

    # Keep /sheet/new compact at 6 system cards (one unified D&D 5e card).
    expect(authed_page.locator(".q-card")).to_have_count(6)
    authed_page.locator(".q-card", has_text="Dungeons & Dragons 5e").first.click()

    dlg = active_dialog(authed_page)
    expect(dlg.get_by_text("New Dungeons & Dragons 5e Character")).to_be_visible()
    # Default edition is 2024 Rules (SRD 5.2) with Species label.
    expect(dlg.get_by_text("2024 Rules (SRD 5.2)")).to_be_visible()
    expect(dlg.locator(".q-field__label", has_text=re.compile(r"^Species$"))).to_be_visible()

    fill_field(dlg, "Name", "Valen 2024")
    fill_field(dlg, "Species", "Elf")
    select_quasar_option(authed_page, dlg, "Class", "Fighter")
    dlg.get_by_role("button", name="Create").click()

    expect(authed_page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(authed_page.get_by_text("Valen 2024").first).to_be_visible()

    # --- 1. Weapon Mastery header counter & Weapons tab ---
    eq_card = sheet_card(authed_page, "Equipment")
    expect(eq_card.get_by_text("Masteries 0 / 3")).to_be_visible()
    expect(eq_card.get_by_text("Attuned 0 / 3")).to_be_visible()

    # Weapons tab is active by default — add Longsword from 2024 SRD 5.2 library.
    w_panel = eq_card.locator(".q-tab-panel", has_text="No weapons carried.").first
    expect(w_panel).to_be_visible()
    w_panel.get_by_role("button", name="Add from Library").click()

    w_dlg = active_dialog(authed_page)
    expect(w_dlg.get_by_text("Add Weapon from Library")).to_be_visible()
    select_quasar_option(authed_page, w_dlg, "Choose weapon", "Longsword", filterable=True)
    w_dlg.get_by_role("button", name="Add").click()
    expect(w_dlg).to_be_hidden()

    # Verify Ma column, Mastery: Sap badge in Properties, hover tooltip rule text, and expanded text.
    w_panel = eq_card.locator(".q-tab-panel", has_text="Longsword").first
    expect(w_panel.get_by_text("Ma", exact=True)).to_be_visible()
    mastery_badge = w_panel.get_by_text("Mastery: Sap")
    expect(mastery_badge).to_be_visible()

    # Hovering the Mastery badge reveals the SRD 5.2 Mastery rule tooltip.
    mastery_badge.hover()
    expect(authed_page.locator(".q-tooltip").last).to_contain_text(
        "Disadvantage on its next attack roll"
    )
    # Move mouse away so tooltip closes before clicking checkboxes.
    eq_card.get_by_text("Equipment").hover()

    # Toggle the 3rd checkbox (Eq=0, At=1, Ma=2) on Longsword row -> Masteries 1 / 3.
    longsword_row = w_panel.locator("div.row", has_text="Longsword").first
    longsword_row.locator(".q-checkbox").nth(2).click()
    expect(eq_card.get_by_text("Masteries 1 / 3")).to_be_visible()

    # Expand Longsword to inspect the SRD 5.2 Mastery rule text.
    w_panel.get_by_text("Longsword", exact=True).click()
    expect(w_panel.get_by_text("Disadvantage on its next attack roll")).to_be_visible()

    # Edit Weapon Mastery limit via the pencil icon next to Masteries 1 / 3 -> set to 4.
    mastery_hdr = eq_card.locator("div.row", has_text="Masteries 1 / 3").first
    icon_button(mastery_hdr, "edit").first.click()
    m_dlg = active_dialog(authed_page)
    expect(m_dlg.get_by_text("Weapon Mastery Limit")).to_be_visible()
    fill_field(m_dlg, "Mastery limit", "4")
    m_dlg.get_by_role("button", name="Save").click()
    expect(m_dlg).to_be_hidden()
    expect(eq_card.get_by_text("Masteries 1 / 4")).to_be_visible()

    # --- 2. 2024 Tool Markdown & Airship Vehicle seeding ---
    eq_card.get_by_role("tab", name="Items", exact=True).click()
    items_panel = eq_card.locator(".q-tab-panel", has_text="No equipment carried.").first
    expect(items_panel).to_be_visible()

    # Add Alchemist's Supplies (Utilize + Craft 2024 rules, no Allies checkbox).
    items_panel.get_by_role("button", name="Add from Library").click()
    i_dlg = active_dialog(authed_page)
    select_quasar_option(authed_page, i_dlg, "Choose item", "Alchemist's Supplies", filterable=True)
    expect(i_dlg.locator(".q-checkbox", has_text="Allies & Stat Blocks")).to_be_hidden()
    i_dlg.get_by_role("button", name="Add").click()
    expect(i_dlg).to_be_hidden()
    expect(eq_card.get_by_text("Alchemist's Supplies", exact=True)).to_be_visible()
    eq_card.get_by_text("Alchemist's Supplies", exact=True).click()
    expect(eq_card.get_by_text("Identify a substance (DC 15)")).to_be_visible()

    # Add Airship -> checked Vehicle stat-block checkbox + 1-click Stat Block jump.
    eq_card.locator(".q-tab-panel", has_text="Alchemist's Supplies").first.get_by_role(
        "button", name="Add from Library"
    ).click()
    i_dlg = active_dialog(authed_page)
    select_quasar_option(authed_page, i_dlg, "Choose item", "Airship", filterable=True)
    seed_cb = i_dlg.locator(
        ".q-checkbox", has_text="Also create Vehicle stat block in Allies & Stat Blocks"
    )
    expect(seed_cb).to_be_visible()
    expect(seed_cb).to_have_attribute("aria-checked", "true")
    i_dlg.get_by_role("button", name="Add").click()
    expect(i_dlg).to_be_hidden()

    eq_card.get_by_role("button", name="Stat Block").first.click()
    expect(authed_page.get_by_text("40,000 GP")).to_be_visible()

    # --- 3. 2024 Spell Library picker ---
    authed_page.get_by_role("tab", name="Character", exact=True).click()
    feat_card = sheet_card(authed_page, "Abilities, Magic & Features")
    expect(feat_card).to_be_visible()
    feat_card.get_by_role("tab", name="Magic", exact=True).click()
    m_panel = feat_card.locator(".q-tab-panel", has_text="Add Magic Resource").first
    expect(m_panel).to_be_visible()
    m_panel.get_by_role("button", name="Add Magic Resource").click()
    res_dlg = active_dialog(authed_page)
    res_dlg.get_by_role("button", name="Add").click()
    expect(res_dlg).to_be_hidden()

    add_sp_btn = feat_card.get_by_role("button", name="Add Spell")
    expect(add_sp_btn).to_be_visible()
    add_sp_btn.click()
    sp_dlg = active_dialog(authed_page)
    select_quasar_option(
        authed_page,
        sp_dlg,
        "Pick from Library (optional)",
        "Chill Touch (Cantrip · Necromancy)",
        filterable=True,
    )
    expect(sp_dlg.get_by_label("Name", exact=True)).to_have_value("Chill Touch")
    sp_dlg.get_by_role("button", name="Add").click()
    expect(sp_dlg).to_be_hidden()
    expect(feat_card.get_by_text("Chill Touch", exact=True)).to_be_visible()

    # --- 4. Reload persistence & /characters badge ---
    authed_page.reload()
    eq_card = sheet_card(authed_page, "Equipment")
    expect(eq_card.get_by_text("Masteries 1 / 4")).to_be_visible()

    authed_page.goto(f"{base}/characters")
    valen_row = authed_page.locator("tr", has_text="Valen 2024").first
    expect(valen_row.get_by_text("Dungeons & Dragons 5e (2024)")).to_be_visible()


def test_dnd_2014_edition_picker_switch_and_classic_flow(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """Switch the D&D 5e New Character edition picker to 2014 Rules (SRD 5.1) and verify:
    1. Origin label dynamically updates back to 'Ancestry / Race'.
    2. 2014 sheet hides Weapon Mastery counter & 'Ma' column while keeping Attunement.
    3. 2014 Longsword shows 'Versatile (1d10)' without any Mastery badge.
    4. 2014 Warhorse seeds Mount stat block on Allies & Stat Blocks.
    5. 2014 Spell Library picker loads 'Fireball'.
    6. '/characters' lists the character with classic 'Dungeons & Dragons 5e' badge.
    """
    base = e2e_server["base_url"]
    authed_page.goto(f"{base}/sheet/new")
    authed_page.locator(".q-card", has_text="Dungeons & Dragons 5e").first.click()

    dlg = active_dialog(authed_page)
    expect(dlg.get_by_text("New Dungeons & Dragons 5e Character")).to_be_visible()

    # Switch edition from 2024 to 2014 -> label flips from Species to Ancestry / Race.
    select_quasar_option(authed_page, dlg, "Ruleset / Edition", "2014 Rules (SRD 5.1)")
    expect(dlg.locator(".q-field__label", has_text=re.compile(r"^Ancestry / Race$"))).to_be_visible()

    fill_field(dlg, "Name", "Aldric 2014")
    fill_field(dlg, "Ancestry / Race", "Human")
    select_quasar_option(authed_page, dlg, "Class", "Fighter")
    dlg.get_by_role("button", name="Create").click()

    expect(authed_page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(authed_page.get_by_text("Aldric 2014").first).to_be_visible()

    # --- 1. No Weapon Mastery UI on 2014 sheets ---
    eq_card = sheet_card(authed_page, "Equipment")
    expect(eq_card.get_by_text("Attuned 0 / 3")).to_be_visible()
    expect(eq_card.get_by_text(re.compile(r"^Masteries \d+ / \d+$"))).to_have_count(0)

    # Add 2014 Longsword from library -> Versatile (1d10), no Ma column or Mastery badge.
    w_panel = eq_card.locator(".q-tab-panel", has_text="No weapons carried.").first
    w_panel.get_by_role("button", name="Add from Library").click()
    w_dlg = active_dialog(authed_page)
    select_quasar_option(authed_page, w_dlg, "Choose weapon", "Longsword", filterable=True)
    w_dlg.get_by_role("button", name="Add").click()
    expect(w_dlg).to_be_hidden()

    w_panel = eq_card.locator(".q-tab-panel", has_text="Longsword").first
    expect(w_panel.get_by_text("Versatile (1d10)")).to_be_visible()
    expect(w_panel.get_by_text("Ma", exact=True)).to_have_count(0)
    expect(w_panel.get_by_text(re.compile(r"Mastery:"))).to_have_count(0)

    # --- 2. 2014 Mount seeding (Warhorse) ---
    eq_card.get_by_role("tab", name="Items", exact=True).click()
    items_panel = eq_card.locator(".q-tab-panel", has_text="No equipment carried.").first
    expect(items_panel).to_be_visible()
    items_panel.get_by_role("button", name="Add from Library").click()

    i_dlg = active_dialog(authed_page)
    select_quasar_option(authed_page, i_dlg, "Choose item", "Warhorse", filterable=True)
    seed_cb = i_dlg.locator(
        ".q-checkbox",
        has_text=re.compile(r"Also create (Mount|Companion) stat block in Allies & Stat Blocks"),
    )
    expect(seed_cb).to_be_visible()
    expect(seed_cb).to_have_attribute("aria-checked", "true")
    i_dlg.get_by_role("button", name="Add").click()
    expect(i_dlg).to_be_hidden()

    eq_card.get_by_role("button", name="Stat Block").first.click()
    expect(authed_page.get_by_text("Trampling Charge")).to_be_visible()

    # --- 3. 2014 Spell Library picker ---
    authed_page.get_by_role("tab", name="Character", exact=True).click()
    feat_card = sheet_card(authed_page, "Abilities, Magic & Features")
    expect(feat_card).to_be_visible()
    feat_card.get_by_role("tab", name="Magic", exact=True).click()
    m_panel = feat_card.locator(".q-tab-panel", has_text="Add Magic Resource").first
    expect(m_panel).to_be_visible()
    m_panel.get_by_role("button", name="Add Magic Resource").click()
    res_dlg = active_dialog(authed_page)
    res_dlg.get_by_role("button", name="Add").click()
    expect(res_dlg).to_be_hidden()

    add_sp_btn = feat_card.get_by_role("button", name="Add Spell")
    expect(add_sp_btn).to_be_visible()
    add_sp_btn.click()
    sp_dlg = active_dialog(authed_page)
    select_quasar_option(
        authed_page,
        sp_dlg,
        "Pick from Library (optional)",
        "Fireball (Lvl 3 · Evocation)",
        filterable=True,
    )
    expect(sp_dlg.get_by_label("Name", exact=True)).to_have_value("Fireball")
    sp_dlg.get_by_role("button", name="Add").click()
    expect(sp_dlg).to_be_hidden()
    expect(feat_card.get_by_text("Fireball", exact=True)).to_be_visible()

    # --- 4. /characters shows classic 2014 style badge ---
    authed_page.goto(f"{base}/characters")
    aldric_row = authed_page.locator("tr", has_text="Aldric 2014").first
    expect(aldric_row.get_by_text("Dungeons & Dragons 5e", exact=True)).to_be_visible()
