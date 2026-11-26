"""
AI Helper Docstring
Purpose: End-to-end "sample play session" Playwright test exercising every
play-time interactive control on a character sheet and creature catalog:
HP slider, Temp HP / Fatigue / Strife / Hit Dice +/- adjusters, Death Save
checkboxes, ability tracker widgets (checkboxes, slider, number), Magic Points
and Extra Resource +/- adjusters, spell filters, Currency & Item quantity +/-
adjusters, inline Weapon/Armor/Item Attunement checkboxes + cap editor, Short
Rest vs Long Rest recovery rules, reload persistence, and Creature Catalog
Public checkbox + 2-column toggle.
Interactions:
- Imports `examples/Torak Vermil.json` for a fast, realistic Level-5 A5e sheet.
- Uses fixtures from `tests/e2e/conftest.py` and helpers from `tests/e2e/helpers.py`.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.conftest import REPO_ROOT
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


def _import_and_open_torak(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/characters")
    expect(page.get_by_text("My Characters").first).to_be_visible()

    page.get_by_role("button", name="Import").click()
    dlg = active_dialog(page)
    dlg.locator("input[type='file']").set_input_files(str(TORAK_EXAMPLE_JSON))
    expect(dlg).to_be_hidden()

    table = page.locator(".q-table")
    expect(table.get_by_text("Torak Vermil").first).to_be_visible()
    table.locator("tbody tr", has_text="Torak Vermil").first.click()
    expect(page).to_have_url(re.compile(r"/character/[0-9a-f-]+"))
    expect(page.get_by_text("39/39")).to_be_visible()


def _exercise_hp_card_controls(page: Page) -> None:
    hp_card = sheet_card(page, "Hit Points")

    # 1. HP Slider (ui.slider): click near the midpoint of the track so HP drops
    # from 39 to ~19-20 via a real pointer interaction, updating both card and top bar.
    slider = hp_card.locator(".q-slider").first
    slider.scroll_into_view_if_needed()
    box = slider.bounding_box()
    assert box is not None
    slider_handle = slider.element_handle()
    slider.click(position={"x": box["width"] * 0.5, "y": box["height"] * 0.5})
    page.wait_for_function("el => !el.isConnected", arg=slider_handle)

    hp_val_text = (
        hp_card.locator(".border-b", has_text="Current / Max")
        .first.locator(".font-bold")
        .inner_text()
    )
    current_hp = int(hp_val_text.split("/")[0].strip())
    assert 10 <= current_hp <= 30, f"Expected slider click to lower HP from 39, got {hp_val_text!r}"
    expect(page.get_by_text(f"{current_hp}/39")).to_be_visible()

    # 2. Temp HP +/- adjuster: 0 -> 1 -> 2 -> 1.
    temp_row = hp_card.locator(".border-b", has_text="Temporary").first
    click_and_wait_refresh(page, icon_button(temp_row, "add").first)
    expect(hp_card.locator(".border-b", has_text="Temporary").first).to_contain_text("1")
    click_and_wait_refresh(
        page, icon_button(hp_card.locator(".border-b", has_text="Temporary").first, "add").first
    )
    expect(hp_card.locator(".border-b", has_text="Temporary").first).to_contain_text("2")
    click_and_wait_refresh(
        page, icon_button(hp_card.locator(".border-b", has_text="Temporary").first, "remove").first
    )
    expect(hp_card.locator(".border-b", has_text="Temporary").first).to_contain_text("1")

    # 3. Fatigue (A5e exhaustion label) +/- adjuster: 0/6 -> 1/6 -> 0/6.
    fat_row = hp_card.locator(".border-b", has_text="Fatigue").first
    click_and_wait_refresh(page, icon_button(fat_row, "add").first)
    expect(hp_card.locator(".border-b", has_text="Fatigue").first).to_contain_text("1 / 6")
    click_and_wait_refresh(
        page, icon_button(hp_card.locator(".border-b", has_text="Fatigue").first, "remove").first
    )
    expect(hp_card.locator(".border-b", has_text="Fatigue").first).to_contain_text("0 / 6")

    # 4. Strife +/- adjuster: 0/6 -> 1/6 -> 0/6.
    strife_row = hp_card.locator(".border-b", has_text="Strife").first
    click_and_wait_refresh(page, icon_button(strife_row, "add").first)
    expect(hp_card.locator(".border-b", has_text="Strife").first).to_contain_text("1 / 6")
    click_and_wait_refresh(
        page, icon_button(hp_card.locator(".border-b", has_text="Strife").first, "remove").first
    )
    expect(hp_card.locator(".border-b", has_text="Strife").first).to_contain_text("0 / 6")

    # 5. Hit Dice +/- adjuster: 5/5 -> 4/5 -> 5/5.
    hd_row = hp_card.locator(".border-b", has_text="HD (Fighter d10)").first
    click_and_wait_refresh(page, icon_button(hd_row, "remove").first)
    expect(hp_card.locator(".border-b", has_text="HD (Fighter d10)").first).to_contain_text("4 / 5")
    click_and_wait_refresh(
        page, icon_button(hp_card.locator(".border-b", has_text="HD (Fighter d10)").first, "add").first
    )
    expect(hp_card.locator(".border-b", has_text="HD (Fighter d10)").first).to_contain_text("5 / 5")

    # 6. Death Saves checkboxes (Successes & Failures).
    succ_row = hp_card.locator(".border-b", has_text="Death Saves — Successes").first
    click_and_wait_refresh(page, succ_row.locator(".q-checkbox").nth(1))
    succ_row = hp_card.locator(".border-b", has_text="Death Saves — Successes").first
    expect(succ_row.locator(".q-checkbox").nth(0)).to_have_attribute("aria-checked", "true")
    expect(succ_row.locator(".q-checkbox").nth(1)).to_have_attribute("aria-checked", "true")
    expect(succ_row.locator(".q-checkbox").nth(2)).to_have_attribute("aria-checked", "false")

    # Unchecking #2 drops successes from 2 -> 1.
    click_and_wait_refresh(page, succ_row.locator(".q-checkbox").nth(1))
    succ_row = hp_card.locator(".border-b", has_text="Death Saves — Successes").first
    expect(succ_row.locator(".q-checkbox").nth(0)).to_have_attribute("aria-checked", "true")
    expect(succ_row.locator(".q-checkbox").nth(1)).to_have_attribute("aria-checked", "false")

    fail_row = hp_card.locator(".border-b", has_text="Death Saves — Failures").first
    click_and_wait_refresh(page, fail_row.locator(".q-checkbox").nth(0))
    fail_row = hp_card.locator(".border-b", has_text="Death Saves — Failures").first
    expect(fail_row.locator(".q-checkbox").nth(0)).to_have_attribute("aria-checked", "true")


def _exercise_ability_tracker_widgets(page: Page) -> None:
    feat_card = sheet_card(page, "Abilities, Magic & Features")

    # Add a 6-use ability (5 <= max < 10 -> renders slider tracker).
    feat_card.get_by_role("button", name="Add Ability / Feature").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Rune Charges")
    select_quasar_option(page, dlg, "Source", "Class")
    fill_field(dlg, "Description", "Slider-tracked rune pool.")
    set_checkbox(dlg, "Track uses", True)
    fill_field(dlg, "Max uses", "6")
    select_quasar_option(page, dlg, "Reset on", "short")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Add a 12-use ability (max >= 10 -> renders number-input tracker).
    feat_card.get_by_role("button", name="Add Ability / Feature").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Arrow Quiver")
    select_quasar_option(page, dlg, "Source", "Class")
    fill_field(dlg, "Description", "Number-tracked quiver.")
    set_checkbox(dlg, "Track uses", True)
    fill_field(dlg, "Max uses", "12")
    select_quasar_option(page, dlg, "Reset on", "long")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Spend 1 long-rest use on Blood Feasting (checkbox tracker: 4/4 -> 3/4).
    bf_exp = feat_card.locator(".q-expansion-item", has_text="Blood Feasting").first
    bf_exp.locator(".q-expansion-item__container > .q-item").first.click()
    bf_content = bf_exp.locator(".q-expansion-item__content").first
    expect(bf_content).to_contain_text("Uses (4/4, resets long)")
    click_and_wait_refresh(page, bf_content.locator(".q-checkbox").first)
    expect(bf_content).to_be_visible()
    expect(bf_content).to_contain_text("Uses (3/4, resets long)")

    # Switch to Class tab: spend Battle Ready (short rest), test slider tracker, test number tracker.
    feat_card.get_by_role("tab", name="Class", exact=True).click()
    br_exp = feat_card.locator(".q-expansion-item", has_text="Fighting Style: Battle Ready").first
    br_exp.locator(".q-expansion-item__container > .q-item").first.click()
    br_content = br_exp.locator(".q-expansion-item__content").first
    expect(br_content).to_contain_text("Uses (1/1, resets short)")
    click_and_wait_refresh(page, br_content.locator(".q-checkbox").first)
    expect(br_content).to_contain_text("Uses (0/1, resets short)")

    # Slider tracker on Rune Charges (6/6 -> lower via slider click).
    rc_exp = feat_card.locator(".q-expansion-item", has_text="Rune Charges").first
    rc_exp.locator(".q-expansion-item__container > .q-item").first.click()
    rc_content = rc_exp.locator(".q-expansion-item__content").first
    expect(rc_content).to_contain_text("Uses (6/6, resets short)")
    rc_slider = rc_content.locator(".q-slider").first
    rc_slider.scroll_into_view_if_needed()
    rc_box = rc_slider.bounding_box()
    assert rc_box is not None
    rc_handle = rc_slider.element_handle()
    rc_slider.click(position={"x": rc_box["width"] * 0.5, "y": rc_box["height"] * 0.5})
    page.wait_for_function("el => !el.isConnected", arg=rc_handle)
    expect(rc_content).to_be_visible()
    expect(rc_content).not_to_contain_text("Uses (6/6, resets short)")

    # Number tracker on Arrow Quiver (12/12 -> 9/12).
    aq_exp = feat_card.locator(".q-expansion-item", has_text="Arrow Quiver").first
    aq_exp.locator(".q-expansion-item__container > .q-item").first.click()
    aq_content = aq_exp.locator(".q-expansion-item__content").first
    expect(aq_content).to_contain_text("Uses (12/12, resets long)")
    aq_inp = aq_content.locator("input").first
    aq_handle = aq_inp.element_handle()
    aq_inp.fill("9")
    page.wait_for_function("el => !el.isConnected", arg=aq_handle)
    expect(aq_content).to_be_visible()
    expect(aq_content).to_contain_text("Uses (9/12, resets long)")


def _exercise_magic_points_extra_resource_and_filters(page: Page) -> None:
    feat_card = sheet_card(page, "Abilities, Magic & Features")
    feat_card.get_by_role("tab", name="Magic", exact=True).click()
    m_panel = feat_card.locator(".q-tab-panel", has_text="Add Magic Resource").first
    expect(m_panel).to_be_visible()

    # Add a Points pool resource WITH an extra resource tracker (Sorcery Points).
    m_panel.get_by_role("button", name="Add Magic Resource").click()
    dlg = active_dialog(page)
    fill_field(dlg, "Name", "Arcane Pool")
    fill_field(dlg, "Source (class/feat/item)", "Feat")
    select_quasar_option(page, dlg, "Magic Type", "Spell Points")
    select_quasar_option(page, dlg, "Attribute", "CHA")
    fill_field(dlg, "Slots (comma-separated, e.g. 4,2)", "10")
    set_checkbox(dlg, "Add extra resource tracker (e.g. Sorcery Points)", True)
    fill_field(dlg, "Resource Name", "Sorcery Points")
    fill_field(dlg, "Maximum", "5")
    select_quasar_option(page, dlg, "Recharges on", "short")
    dlg.get_by_role("button", name="Add").click()
    expect(dlg).to_be_hidden()

    # Expand Arcane Pool and exercise both Points +/- and Extra Resource +/- adjusters.
    ap_exp = feat_card.locator(".q-expansion-item", has_text="Arcane Pool (Spell Points)").first
    ap_exp.locator(".q-expansion-item__container > .q-item").first.click()
    ap_content = ap_exp.locator(".q-expansion-item__content").first
    expect(ap_content).to_be_visible()
    expect(ap_content).to_contain_text("Points: 10 / 10")
    expect(ap_content).to_contain_text("Sorcery Points:")
    expect(ap_content).to_contain_text("5 / 5")

    pts_row = ap_content.locator("div.row", has_text="Points: 10 / 10").first
    click_and_wait_refresh(page, icon_button(pts_row, "remove").first)
    expect(ap_content).to_be_visible()
    expect(ap_content).to_contain_text("Points: 9 / 10")
    pts_row = ap_content.locator("div.row", has_text="Points: 9 / 10").first
    click_and_wait_refresh(page, icon_button(pts_row, "add").first)
    expect(ap_content).to_contain_text("Points: 10 / 10")

    er_row = ap_content.locator(".border", has_text="Sorcery Points:").first
    click_and_wait_refresh(page, icon_button(er_row, "remove").first)
    expect(ap_content).to_contain_text("4 / 5")
    er_row = ap_content.locator(".border", has_text="Sorcery Points:").first
    click_and_wait_refresh(page, icon_button(er_row, "add").first)
    expect(ap_content).to_contain_text("5 / 5")

    # Test Prepared and Ritual spell filters (Torak has no ritual spells -> empty message).
    set_checkbox(feat_card, "Prepared", True)
    expect(feat_card.locator(".cursor-pointer", has_text="Hoarfrost").first).to_be_visible()
    set_checkbox(feat_card, "Ritual", True)
    expect(feat_card.get_by_text("No spells match the active filters.")).to_be_visible()
    set_checkbox(feat_card, "Ritual", False)
    set_checkbox(feat_card, "Prepared", False)
    expect(feat_card.locator(".cursor-pointer", has_text="Hoarfrost").first).to_be_visible()


def _exercise_equipment_play_controls(page: Page) -> None:
    eq_card = sheet_card(page, "Equipment")
    expect(eq_card.get_by_text("Attuned 0 / 3")).to_be_visible()

    # 1. Currency +/- buttons on GP (115 -> 116 -> 115).
    eq_card.get_by_role("tab", name="Currency", exact=True).click()
    gp_box = eq_card.locator(".border").filter(
        has=page.locator("div", has_text=re.compile(r"^GP$"))
    ).first
    expect(gp_box.locator("input").first).to_have_value("115")
    click_and_wait_refresh(page, icon_button(gp_box, "add").first)
    gp_box = eq_card.locator(".border").filter(
        has=page.locator("div", has_text=re.compile(r"^GP$"))
    ).first
    expect(gp_box.locator("input").first).to_have_value("116")
    click_and_wait_refresh(page, icon_button(gp_box, "remove").first)
    gp_box = eq_card.locator(".border").filter(
        has=page.locator("div", has_text=re.compile(r"^GP$"))
    ).first
    expect(gp_box.locator("input").first).to_have_value("115")

    # 2. Weapons inline Attuned checkbox (2nd checkbox on weapon row: [Eq, At]).
    eq_card.get_by_role("tab", name="Weapons", exact=True).click()
    w_row = eq_card.locator(".border-b", has_text="Longsword + 1").first
    expect(w_row).to_be_visible()
    click_and_wait_refresh(page, w_row.locator(".q-checkbox").nth(1))
    expect(eq_card.get_by_text("Attuned 1 / 3")).to_be_visible()

    # 3. Armor inline Attuned checkboxes on Half plate & Medium Shield -> 3 / 3.
    eq_card.get_by_role("tab", name="Armor", exact=True).click()
    hp_armor_row = eq_card.locator(".border-b", has_text="Half plate (steel)").first
    expect(hp_armor_row).to_be_visible()
    click_and_wait_refresh(page, hp_armor_row.locator(".q-checkbox").nth(1))
    expect(eq_card.get_by_text("Attuned 2 / 3")).to_be_visible()

    shield_row = eq_card.locator(".border-b", has_text="Medium Shield").first
    click_and_wait_refresh(page, shield_row.locator(".q-checkbox").nth(1))
    expect(eq_card.get_by_text("Attuned 3 / 3")).to_be_visible()

    # 4. Items tab: quantity +/- on Torch (9 -> 10 -> 9) + inline Attuned checkbox (4 / 3 over-cap!).
    eq_card.get_by_role("tab", name="Items", exact=True).click()
    torch_row = eq_card.locator(".border-b", has_text="Torch").first
    expect(torch_row).to_be_visible()
    expect(torch_row).to_contain_text("9")
    click_and_wait_refresh(page, icon_button(torch_row, "add").first)
    torch_row = eq_card.locator(".border-b", has_text="Torch").first
    expect(torch_row).to_contain_text("10")
    click_and_wait_refresh(page, icon_button(torch_row, "remove").first)
    torch_row = eq_card.locator(".border-b", has_text="Torch").first
    expect(torch_row).to_contain_text("9")

    potion_row = eq_card.locator(".border-b", has_text="Potion of Hill Giant Strength").first
    click_and_wait_refresh(page, potion_row.locator(".q-checkbox").first)
    attuned_lbl = eq_card.get_by_text("Attuned 4 / 3")
    expect(attuned_lbl).to_be_visible()
    expect(attuned_lbl).to_have_class(re.compile(r"text-red-400"))

    # 5. Edit Attunement Limit bonus (+1 -> 4 / 4, no longer red), then un-attune potion -> 3 / 4.
    eq_header = eq_card.locator("div.row").first
    icon_button(eq_header, "edit").first.click()
    dlg = active_dialog(page)
    expect(dlg.get_by_text("Attunement Limit")).to_be_visible()
    fill_field(dlg, "Limit bonus", "1")
    dlg.get_by_role("button", name="Save").click()
    expect(dlg).to_be_hidden()
    expect(eq_card.get_by_text("Attuned 4 / 4")).to_be_visible()

    potion_row = eq_card.locator(".border-b", has_text="Potion of Hill Giant Strength").first
    click_and_wait_refresh(page, potion_row.locator(".q-checkbox").first)
    expect(eq_card.get_by_text("Attuned 3 / 4")).to_be_visible()


def _exercise_short_and_long_rests_and_reload(page: Page) -> None:
    # 1. Short Rest: spend 1 Fighter d10 Hit Die -> HD drops 5/5 -> 4/5,
    # short-rest ability resets (Battle Ready 0/1 -> 1/1), long-rest ability stays 3/4.
    page.get_by_role("button", name="Short Rest").click()
    dlg = active_dialog(page)
    expect(dlg.get_by_text("Short Rest")).to_be_visible()
    fill_field(dlg, "Spend", "1")
    dlg.get_by_role("button", name="Confirm").click()
    expect(dlg).to_be_hidden()

    hp_card = sheet_card(page, "Hit Points")
    expect(hp_card.locator(".border-b", has_text="HD (Fighter d10)").first).to_contain_text("4 / 5")

    feat_card = sheet_card(page, "Abilities, Magic & Features")
    feat_card.get_by_role("tab", name="Abilities", exact=True).click()
    feat_card.get_by_role("tab", name="Class", exact=True).click()
    br_exp = feat_card.locator(".q-expansion-item", has_text="Fighting Style: Battle Ready").first
    expect(br_exp.locator(".q-expansion-item__content")).to_contain_text("Uses (1/1, resets short)")

    feat_card.get_by_role("tab", name="Heritage", exact=True).click()
    bf_exp = feat_card.locator(".q-expansion-item", has_text="Blood Feasting").first
    expect(bf_exp.locator(".q-expansion-item__content")).to_contain_text("Uses (3/4, resets long)")

    # 2. Long Rest: restores HP to 39/39, restores Blood Feasting 4/4, clears Death Saves.
    page.get_by_role("button", name="Long Rest").click()
    dlg = active_dialog(page)
    dlg.get_by_role("button", name="Confirm").click()
    expect(dlg).to_be_hidden()

    expect(hp_card.get_by_text("39 / 39")).to_be_visible()
    expect(bf_exp.locator(".q-expansion-item__content")).to_contain_text("Uses (4/4, resets long)")

    # 3. Reload verifies persisted state across all play-session mutations.
    page.reload()
    expect(page.get_by_text("39/39")).to_be_visible()
    expect(sheet_card(page, "Equipment").get_by_text("Attuned 3 / 4")).to_be_visible()


def test_play_session_controls_sliders_checkboxes_and_rests(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """Exercise every play-time checkbox, +/- adjuster, slider, and rest flow."""
    _import_and_open_torak(authed_page, e2e_server["base_url"])
    _exercise_hp_card_controls(authed_page)
    _exercise_ability_tracker_widgets(authed_page)
    _exercise_magic_points_extra_resource_and_filters(authed_page)
    _exercise_equipment_play_controls(authed_page)
    _exercise_short_and_long_rests_and_reload(authed_page)


def test_creature_public_checkbox_and_two_column_toggle(
    authed_page: Page, e2e_server: dict[str, str]
) -> None:
    """Verify Creature Catalog Public checkbox and 2-column toggle affect rendering."""
    authed_page.goto(f"{e2e_server['base_url']}/creatures")
    expect(authed_page.get_by_text("Creature Catalog").first).to_be_visible()

    authed_page.get_by_role("button", name="New Creature").click()
    dlg = active_dialog(authed_page)
    fill_field(dlg, "Name*", "Dire Mammoth")
    fill_field(dlg, "Challenge Rating", "6")
    set_checkbox(dlg, "Public — visible to all logged-in users", True)
    # Toggle Columns from 1 to 2.
    dlg.locator(".q-btn-toggle").get_by_role("button", name="2", exact=True).click()
    fill_field(
        dlg,
        "Body (Markdown)",
        "___\n"
        "> ## Dire Mammoth\n"
        "> *Huge Beast*\n"
        "> ___\n"
        "> *Armor Class* 15  \n"
        "> *Hit Points* 180  \n"
        "> *Speed* 40 ft.  \n"
        "> ___\n"
        "> ### Traits\n"
        "> ***Trampling Charge.*** Knock target prone.\n"
        ">\n"
        "> ### Actions\n"
        "> ***Gore.*** *Melee Weapon Attack:* +10 to hit, reach 10 ft. *Hit:* 25 piercing damage.\n"
        ">\n"
        "> ***Stomp.*** *Melee Weapon Attack:* +10 to hit, reach 5 ft. *Hit:* 29 bludgeoning damage.\n"
        ">\n"
        "> ### Legendary Actions\n"
        "> ***Trumpet.*** Nearby enemies must succeed on a Wisdom saving throw or be frightened.\n",
    )
    dlg.get_by_role("button", name="Save").click()
    expect(dlg).to_be_hidden()

    card = authed_page.locator(".q-card", has_text="Dire Mammoth").first
    expect(card.get_by_text("Public", exact=True)).to_be_visible()

    # Expand -> verify 2-column `.phb-cols-2` class is applied AND content actually
    # balances across both left and right columns inside the stat-block blockquote.
    card.locator(".cursor-pointer", has_text="Dire Mammoth").first.click()
    phb = card.locator(".phb.phb-cols-2")
    expect(phb).to_be_visible()
    expect(card.get_by_text("Trampling Charge.")).to_be_visible()

    bq = phb.locator("blockquote").first
    bq_box = bq.bounding_box()
    title_box = bq.locator("h2", has_text="Dire Mammoth").first.bounding_box()
    leg_box = bq.locator("h3", has_text="Legendary Actions").first.bounding_box()
    assert bq_box and title_box and leg_box
    assert title_box["x"] < bq_box["x"] + bq_box["width"] * 0.3
    assert leg_box["x"] > bq_box["x"] + bq_box["width"] * 0.45

    # Clean up.
    icon_button(card, "delete").click()
    del_dlg = active_dialog(authed_page)
    del_dlg.get_by_role("button", name="Delete").click()
    expect(del_dlg).to_be_hidden()
    expect(authed_page.locator(".q-card", has_text="Dire Mammoth")).to_have_count(0)
