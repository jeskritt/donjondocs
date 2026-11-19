"""
AI Helper Docstring
Purpose: Playwright E2E smoke tests for non-A5e rule-system UI branches:
- Shadowdark RPG (suppresses Skills card, Attunement, Combat Maneuvers tab,
  Inspiration, PROF chip, and Vehicle ally-type suggestion; GP-only currency).
- Ultramodern5 Magus (auto-checks and locks Vigor on the creation dialog,
  surfaces the 7th VIG attribute, uses `$` currency, and renders DARK magic
  with Vessel/River/VR stats, +/- pool spend, and "River" spell filter label).
Interactions:
- Uses fixtures from `tests/e2e/conftest.py` and helpers from `tests/e2e/helpers.py`.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import (
    active_dialog,
    click_and_wait_refresh,
    fill_field,
    icon_button,
    select_quasar_option,
    sheet_card,
)


def test_shadowdark_ui_suppressions_and_currency(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """Shadowdark sheets hide 5e-only chrome (skills, attunement, maneuvers, inspiration, PROF, Vehicle)."""
    authed_page.goto(f"{e2e_server['base_url']}/sheet/new")
    authed_page.locator(".q-card", has_text="Shadowdark RPG").first.click()
    dlg = active_dialog(authed_page)
    fill_field(dlg, "Name", "Vex the Torchbearer")
    select_quasar_option(authed_page, dlg, "Class", "Fighter")
    dlg.get_by_role("button", name="Create").click()

    expect(authed_page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(authed_page.get_by_text("Vex the Torchbearer").first).to_be_visible()

    # Skills card, Attuned header, Combat Maneuvers tab, Inspiration row, and PROF chip are hidden.
    expect(
        authed_page.locator(".q-card").filter(
            has=authed_page.locator(".text-xl", has_text=re.compile(r"^Skills$"))
        )
    ).to_have_count(0)
    expect(authed_page.get_by_text(re.compile(r"^Attuned \d+ / \d+$"))).to_have_count(0)
    feat_card = sheet_card(authed_page, "Abilities, Magic & Features")
    expect(feat_card.get_by_role("tab", name="Combat Maneuvers", exact=True)).to_have_count(0)
    def_card = sheet_card(authed_page, "Defenses")
    expect(def_card.get_by_text("Inspiration", exact=True)).to_have_count(0)
    expect(authed_page.locator(".text-xs", has_text=re.compile(r"^PROF$"))).to_have_count(0)

    # Currency tab shows GP only (no SP/CP/EP/PP).
    eq_card = sheet_card(authed_page, "Equipment")
    eq_card.get_by_role("tab", name="Currency", exact=True).click()
    expect(
        eq_card.locator(".border").filter(
            has=authed_page.locator("div", has_text=re.compile(r"^GP$"))
        )
    ).to_be_visible()
    expect(
        eq_card.locator(".border").filter(
            has=authed_page.locator("div", has_text=re.compile(r"^SP$"))
        )
    ).to_have_count(0)

    # Allies tab: "Vehicle" is omitted from Shadowdark's type suggestions.
    authed_page.get_by_role("tab", name="Allies & Stat Blocks", exact=True).click()
    authed_page.get_by_role("button", name="Add Ally").click()
    ally_dlg = active_dialog(authed_page)
    type_select = ally_dlg.locator(".q-select").filter(
        has=authed_page.locator(".q-field__label", has_text=re.compile(r"^Type$"))
    ).first
    type_select.click()
    menu = authed_page.locator(".q-menu").last
    expect(menu).to_be_visible()
    expect(menu.locator(".q-item", has_text="Pet")).to_be_visible()
    expect(menu.locator(".q-item", has_text="Vehicle")).to_have_count(0)


def test_um5_magus_vigor_lock_and_dark_magic(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """UM5 Magus force-enables Vigor, surfaces VIG + `$` currency, and renders DARK magic."""
    authed_page.goto(f"{e2e_server['base_url']}/sheet/new")
    authed_page.locator(".q-card", has_text="Ultramodern5").first.click()
    dlg = active_dialog(authed_page)
    fill_field(dlg, "Name", "Kaelen Voss")

    # Picking Magus (a Vigor-caster) auto-checks and disables the Include Vigor checkbox.
    vigor_box = dlg.locator(".q-checkbox", has_text="Include Vigor").first
    expect(vigor_box).to_have_attribute("aria-checked", "false")
    select_quasar_option(authed_page, dlg, "Class", "Magus")
    expect(vigor_box).to_have_attribute("aria-checked", "true")
    expect(vigor_box).to_have_attribute("aria-disabled", "true")
    dlg.get_by_role("button", name="Create").click()

    expect(authed_page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(authed_page.get_by_text("Kaelen Voss").first).to_be_visible()

    # 7th attribute VIG renders in Abilities & Saves.
    ab_card = sheet_card(authed_page, "Abilities & Saves")
    expect(
        ab_card.locator("div.row").filter(
            has=authed_page.locator("div", has_text=re.compile(r"^VIG$"))
        ).first
    ).to_be_visible()

    # Currency tab shows `$`.
    eq_card = sheet_card(authed_page, "Equipment")
    eq_card.get_by_role("tab", name="Currency", exact=True).click()
    expect(
        eq_card.locator(".border").filter(
            has=authed_page.locator("div", has_text=re.compile(r"^\$$"))
        )
    ).to_be_visible()

    # Magic tab: add a DARK resource -> auto-defaults Attribute to VIG, shows Vessel/River/VR.
    feat_card = sheet_card(authed_page, "Abilities, Magic & Features")
    feat_card.get_by_role("tab", name="Magic", exact=True).click()
    m_panel = feat_card.locator(".q-tab-panel", has_text="Add Magic Resource").first
    expect(m_panel).to_be_visible()

    m_panel.get_by_role("button", name="Add Magic Resource").click()
    m_dlg = active_dialog(authed_page)
    fill_field(m_dlg, "Name", "Dark Conduit")
    select_quasar_option(authed_page, m_dlg, "Magic Type", "Dark")
    expect(m_dlg.get_by_text("Vessel (base)")).to_be_visible()
    fill_field(m_dlg, "Vessel (base)", "10")
    fill_field(m_dlg, "Current Dark", "10")
    fill_field(m_dlg, "VR base", "2")
    m_dlg.get_by_role("button", name="Add").click()
    expect(m_dlg).to_be_hidden()

    # Expand DARK resource: verify VIG attribute, Dark pool +/- spend, River/VR, and "River" filter.
    dk_exp = feat_card.locator(".q-expansion-item", has_text="Dark Conduit (Dark)").first
    dk_exp.locator(".q-expansion-item__container > .q-item").first.click()
    dk_content = dk_exp.locator(".q-expansion-item__content").first
    expect(dk_content).to_be_visible()
    expect(dk_content).to_contain_text("Attribute: VIG")
    expect(dk_content).to_contain_text("Dark: 10 / 10")
    expect(dk_content).to_contain_text("River:")
    expect(dk_content).to_contain_text("VR: 2")

    dark_row = dk_content.locator("div.row", has_text="Dark: 10 / 10").first
    click_and_wait_refresh(authed_page, icon_button(dark_row, "remove").first)
    expect(dk_content).to_be_visible()
    expect(dk_content).to_contain_text("Dark: 9 / 10")

    # DARK relabels the "Prepared" spell filter to "River".
    expect(feat_card.locator(".q-checkbox", has_text="River").first).to_be_visible()
