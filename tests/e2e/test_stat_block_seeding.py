"""Playwright E2E tests for cross-system Stat Block Seeding, Stat Block jump links, and the Allies Library Picker."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import select_quasar_option


def test_sra2_vehicle_amp_seeds_ally_and_allies_library_picker(
    authed_page: Page, e2e_server: dict[str, str]
):
    """Adding a Shadowrun Vehicle Amp seeds a Vehicle stat block on Allies & Stat Blocks,
    links it via a 1-click Stat Block jump button, and Allies -> Add Ally lets the player
    seed an Allies-only Spirit preset from the Library picker."""
    authed_page.goto(f"{e2e_server['base_url']}/sheet/new")
    authed_page.locator(".q-card").filter(has_text="Shadowrun: Anarchy 2.0").click()
    dlg = authed_page.locator(".q-dialog")
    expect(dlg.get_by_text("New Shadowrun: Anarchy 2.0 Runner")).to_be_visible()
    dlg.get_by_label("Streetname").fill("RiggerX")
    dlg.get_by_role("button", name="Create").click()
    authed_page.wait_for_url(re.compile(r"/character/"))
    expect(authed_page.get_by_text("RiggerX").first).to_be_visible()

    # 1. Add a Vehicle Shadow Amp — checkbox should auto-appear checked.
    amps_card = authed_page.locator(".q-card").filter(
        has=authed_page.get_by_role("button", name="Add Amp")
    ).first
    amps_card.get_by_role("button", name="Add Amp").click()
    amp_dlg = authed_page.locator(".q-dialog")
    expect(amp_dlg.get_by_text("Add Shadow Amp")).to_be_visible()

    select_quasar_option(
        authed_page,
        amp_dlg,
        "Pick Prebuilt Amp / Deck / Vehicle / Drone (copies locally)",
        "Harley-Davidson Centaur (Vehicle)",
        filterable=True,
    )
    seed_cb = amp_dlg.locator(
        ".q-checkbox", has_text="Also create Vehicle stat block in Allies & Stat Blocks"
    )
    expect(seed_cb).to_be_visible()
    expect(seed_cb).to_have_attribute("aria-checked", "true")

    amp_dlg.get_by_role("button", name="Save").click()
    expect(amps_card.get_by_text("Harley-Davidson Centaur (Vehicle)")).to_be_visible()

    # 2. Click the Stat Block jump button -> switches to Allies & Stat Blocks expanded.
    stat_btn = amps_card.get_by_role("button", name="Stat Block").first
    expect(stat_btn).to_be_visible()
    stat_btn.click()

    expect(authed_page.get_by_text("Allies & Stat Blocks").first).to_be_visible()
    expect(authed_page.get_by_text("Damage Thresholds:")).to_be_visible()

    # 3. Seed an Allies-only Spirit preset via the Library / Creature Catalog picker.
    authed_page.get_by_role("button", name="Add Ally").click()
    ally_dlg = authed_page.locator(".q-dialog")
    expect(ally_dlg.get_by_text("Add Ally")).to_be_visible()

    select_quasar_option(
        authed_page,
        ally_dlg,
        "Seed from Library or Creature Catalog (optional)",
        "[Library · Spirit] Spirit of Fire",
        filterable=True,
    )
    expect(ally_dlg.get_by_label("Name")).to_have_value("Spirit of Fire")
    ally_dlg.get_by_role("button", name="Save").click()

    expect(authed_page.get_by_text("Spirit of Fire")).to_be_visible()
    authed_page.get_by_text("Spirit of Fire").click()
    expect(authed_page.get_by_text("Spirit of Fire").first).to_be_visible()

    # 4. Reload and confirm both Allies persisted cleanly.
    authed_page.reload()
    authed_page.get_by_role("tab", name="Allies & Stat Blocks").click()
    allies_panel = authed_page.locator(".q-tab-panel").filter(
        has=authed_page.get_by_role("button", name="Add Ally")
    )
    expect(allies_panel.get_by_text("Harley-Davidson Centaur (Vehicle)")).to_be_visible()
    expect(allies_panel.get_by_text("Spirit of Fire")).to_be_visible()


def test_um5_vehicle_item_seeds_ally_and_jump_link(
    authed_page: Page, e2e_server: dict[str, str]
):
    """Adding a legacy CSV Vehicle item (APC) on an Ultramodern5 character offers
    the checked Allies seeding checkbox, creates the Vehicle stat block, and wires
    the 1-click Stat Block jump button on the Equipment Items row."""
    authed_page.goto(f"{e2e_server['base_url']}/sheet/new")
    authed_page.locator(".q-card").filter(has_text="Ultramodern5").click()
    dlg = authed_page.locator(".q-dialog")
    expect(dlg.get_by_text("New ULTRAMODERN 5E Character")).to_be_visible()
    dlg.get_by_label("Name", exact=True).fill("DriverX")
    dlg.get_by_role("button", name="Create").click()
    authed_page.wait_for_url(re.compile(r"/character/"))
    expect(authed_page.get_by_text("DriverX").first).to_be_visible()

    # Switch Equipment card to the Items tab and wait for its panel before clicking.
    eq_card = authed_page.locator(".q-card").filter(
        has=authed_page.get_by_role("tab", name="Currency")
    ).first
    eq_card.get_by_role("tab", name="Items").click()
    items_panel = eq_card.locator(".q-tab-panel").filter(has_text="No equipment carried.")
    expect(items_panel).to_be_visible()
    items_panel.get_by_role("button", name="Add from Library").click()

    picker_dlg = authed_page.locator(".q-dialog")
    expect(picker_dlg.get_by_text("Add Item from Library")).to_be_visible()
    select_quasar_option(
        authed_page,
        picker_dlg,
        "Choose item",
        "APC",
        filterable=True,
    )
    seed_cb = picker_dlg.locator(
        ".q-checkbox", has_text="Also create Vehicle stat block in Allies & Stat Blocks"
    )
    expect(seed_cb).to_be_visible()
    expect(seed_cb).to_have_attribute("aria-checked", "true")

    picker_dlg.get_by_role("button", name="Add").click()
    expect(eq_card.get_by_text("APC")).to_be_visible()

    # Click Stat Block jump button -> lands on Allies & Stat Blocks with APC expanded.
    stat_btn = eq_card.get_by_role("button", name="Stat Block").first
    expect(stat_btn).to_be_visible()
    stat_btn.click()

    expect(authed_page.get_by_text("Allies & Stat Blocks").first).to_be_visible()
    expect(authed_page.get_by_text("Notes & Modifications")).to_be_visible()


def test_a5e_gear_markdown_mount_seeding_maneuver_and_spell_pickers(
    authed_page: Page, e2e_server: dict[str, str]
):
    """Create a Level Up: Advanced 5e character and verify:
    1. Adding Poisoner's kit populates rich A5e Markdown rules inline (no Allies checkbox).
    2. Adding Mastiff offers the checked Companion stat-block checkbox + 1-click Stat Block jump.
    3. Combat Maneuver Library picker auto-populates Catch Your Breath.
    4. Spell Library picker auto-populates Fireball.
    """
    authed_page.goto(f"{e2e_server['base_url']}/sheet/new")
    authed_page.locator(".q-card").filter(has_text="Level Up: Advanced 5e").click()
    dlg = authed_page.locator(".q-dialog")
    expect(dlg.get_by_text("New LEVEL UP: ADVANCED 5E Character")).to_be_visible()
    dlg.get_by_label("Name", exact=True).fill("AlchemistX")
    dlg.get_by_role("button", name="Create").click()
    authed_page.wait_for_url(re.compile(r"/character/"))
    expect(authed_page.get_by_text("AlchemistX").first).to_be_visible()

    eq_card = authed_page.locator(".q-card").filter(
        has=authed_page.get_by_role("tab", name="Currency")
    ).first
    eq_card.get_by_role("tab", name="Items").click()
    items_panel = eq_card.locator(".q-tab-panel").filter(has_text="No equipment carried.")
    expect(items_panel).to_be_visible()

    # 1. Poisoner's kit -> inline Markdown rules, no Allies seeding checkbox.
    items_panel.get_by_role("button", name="Add from Library").click()
    picker_dlg = authed_page.locator(".q-dialog")
    expect(picker_dlg.get_by_text("Add Item from Library")).to_be_visible()
    select_quasar_option(authed_page, picker_dlg, "Choose item", "Poisoner's kit", filterable=True)
    expect(picker_dlg.locator(".q-checkbox", has_text="Allies & Stat Blocks")).to_be_hidden()
    picker_dlg.get_by_role("button", name="Add").click()
    expect(eq_card.get_by_text("Poisoner's kit", exact=True)).to_be_visible()
    eq_card.get_by_text("Poisoner's kit", exact=True).click()
    expect(eq_card.get_by_text("harvest poisons")).to_be_visible()

    # 2. Mastiff -> Companion seeding checkbox checked + Stat Block jump.
    eq_card.locator(".q-tab-panel").filter(has_text="Poisoner's kit").get_by_role(
        "button", name="Add from Library"
    ).click()
    picker_dlg = authed_page.locator(".q-dialog")
    select_quasar_option(authed_page, picker_dlg, "Choose item", "Mastiff", filterable=True)
    seed_cb = picker_dlg.locator(
        ".q-checkbox", has_text="Also create Companion stat block in Allies & Stat Blocks"
    )
    expect(seed_cb).to_be_visible()
    expect(seed_cb).to_have_attribute("aria-checked", "true")
    picker_dlg.get_by_role("button", name="Add").click()
    expect(eq_card.get_by_text("Mastiff", exact=True)).to_be_visible()

    # Jump to Mastiff stat block on Allies & Stat Blocks.
    eq_card.get_by_role("button", name="Stat Block").first.click()
    expect(authed_page.get_by_text("Keen Hearing and Smell.")).to_be_visible()

    # Switch back to Character tab for Combat Maneuver & Spell library pickers.
    authed_page.get_by_role("tab", name="Character").click()

    feat_card = authed_page.locator(".q-card").filter(
        has_text="Abilities, Magic & Features"
    ).first

    # 3. Combat Maneuver picker -> Catch Your Breath.
    feat_card.get_by_role("tab", name="Combat Maneuvers").click()
    add_man_btn = feat_card.get_by_role("button", name="Add Combat Maneuver")
    expect(add_man_btn).to_be_visible()
    add_man_btn.click()
    man_dlg = authed_page.locator(".q-dialog")
    select_quasar_option(
        authed_page,
        man_dlg,
        "Pick from Library (optional)",
        "Catch Your Breath (Deg 1 · Adamant Mountain)",
        filterable=True,
    )
    expect(man_dlg.get_by_label("Name", exact=True)).to_have_value("Catch Your Breath")
    man_dlg.get_by_role("button", name="Add").click()
    expect(feat_card.get_by_text("Catch Your Breath", exact=True)).to_be_visible()

    # 4. Magic Resource + Spell Library picker -> Fireball.
    feat_card.get_by_role("tab", name="Magic").click()
    add_res_btn = feat_card.get_by_role("button", name="Add Magic Resource")
    expect(add_res_btn).to_be_visible()
    add_res_btn.click()
    res_dlg = authed_page.locator(".q-dialog")
    res_dlg.get_by_role("button", name="Add").click()

    add_sp_btn = feat_card.get_by_role("button", name="Add Spell")
    expect(add_sp_btn).to_be_visible()
    add_sp_btn.click()
    sp_dlg = authed_page.locator(".q-dialog")
    select_quasar_option(
        authed_page,
        sp_dlg,
        "Pick from Library (optional)",
        "Fireball (Lvl 3 · Evocation)",
        filterable=True,
    )
    expect(sp_dlg.get_by_label("Name", exact=True)).to_have_value("Fireball")
    sp_dlg.get_by_role("button", name="Add").click()
    expect(feat_card.get_by_text("Fireball", exact=True)).to_be_visible()
