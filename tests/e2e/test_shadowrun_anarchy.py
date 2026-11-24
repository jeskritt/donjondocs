"""Playwright E2E tests for Shadowrun: Anarchy 2.0 character creation, play controls, and Markdown Amp templates."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import click_and_wait_refresh, select_quasar_option


def test_shadowrun_anarchy_creation_controls_and_markdown_templates(
    authed_page: Page, e2e_server: dict[str, str]
):
    """Create a Shadowrun: Anarchy 2.0 runner, verify no PHB toggle, add a prebuilt
    Cyberdeck Markdown Amp + Cyberware Amp, toggle Wounds & Edge, and verify persistence."""
    authed_page.goto(f"{e2e_server['base_url']}/sheet/new")
    expect(authed_page.get_by_text("Select Game System")).to_be_visible()

    # Regression check: every system card's Select button must stay strictly
    # inside its own card bounds (prevents Quasar flex-wrap horizontal overflow).
    cards = authed_page.locator(".q-card")
    expect(cards).to_have_count(6)
    for i in range(6):
        card = cards.nth(i)
        btn = card.get_by_role("button", name="Select")
        c_box = card.bounding_box()
        b_box = btn.bounding_box()
        assert c_box is not None and b_box is not None
        assert b_box["x"] >= c_box["x"] - 1
        assert b_box["x"] + b_box["width"] <= c_box["x"] + c_box["width"] + 1
        assert b_box["y"] + b_box["height"] <= c_box["y"] + c_box["height"] + 1

    authed_page.locator(".q-card").filter(has_text="Shadowrun: Anarchy 2.0").click()
    dlg = authed_page.locator(".q-dialog")
    expect(dlg.get_by_text("New Shadowrun: Anarchy 2.0 Runner")).to_be_visible()

    dlg.get_by_label("Streetname").fill("Cipher")
    select_quasar_option(authed_page, dlg, "Metatype", "Ork")
    expect(dlg.get_by_text("Starting Edge: 3")).to_be_visible()
    dlg.get_by_role("button", name="Create").click()

    authed_page.wait_for_url(re.compile(r"/character/"))
    expect(authed_page.get_by_text("Cipher").first).to_be_visible()
    expect(authed_page.get_by_text("Ork").first).to_be_visible()

    # PHB style toggle must be absent on Shadowrun: Anarchy 2.0 sheets.
    expect(authed_page.get_by_text("PHB style")).to_have_count(0)

    # Toggle a Serious wound checkbox and Stim Patch switch.
    wounds_card = authed_page.locator(".q-card").filter(has_text="Condition Monitor & Wounds").first
    serious_cb = wounds_card.locator(".q-checkbox", has_text="S1").first
    click_and_wait_refresh(authed_page, serious_cb)
    expect(wounds_card.get_by_text("Disadvantage on all Tests until serious wounds are healed.")).to_be_visible()

    stim_sw = wounds_card.locator(".q-toggle", has_text="Stim Patch").first
    click_and_wait_refresh(authed_page, stim_sw)
    expect(wounds_card.get_by_text("Stim patch active")).to_be_visible()

    # Add a prebuilt Cyberdeck Shadow Amp (MCT 360) and customize its local Markdown copy.
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
        "MCT 360 (Cyberdeck)",
        filterable=True,
    )
    expect(amp_dlg.get_by_label("Amp Name*")).to_have_value("MCT 360 (Cyberdeck)")
    amp_dlg.get_by_role("button", name="Save").click()
    expect(amps_card.get_by_text("MCT 360 (Cyberdeck)")).to_be_visible()

    # Expand the Cyberdeck Amp to verify Markdown stat block rendered cleanly.
    amps_card.get_by_text("MCT 360 (Cyberdeck)").click()
    expect(amps_card.get_by_text("Matrix Damage Monitor:")).to_be_visible()

    # Add Aluminum Bone Lacing (Cyberware -> drops Essence from 6 to 5 and adds 3rd light box).
    amps_card.get_by_role("button", name="Add Amp").click()
    amp_dlg = authed_page.locator(".q-dialog")
    select_quasar_option(
        authed_page,
        amp_dlg,
        "Pick Prebuilt Amp / Deck / Vehicle / Drone (copies locally)",
        "Aluminum Bone Lacing",
        filterable=True,
    )
    amp_dlg.get_by_role("button", name="Save").click()
    expect(amps_card.get_by_text("Aluminum Bone Lacing")).to_be_visible()

    # Verify Essence dropped to 5 / 6 and a 3rd Light wound box (L3) appeared!
    attrs_card = authed_page.locator(".q-card").filter(has_text="Attributes").first
    expect(attrs_card.get_by_text("5 / 6")).to_be_visible()
    expect(wounds_card.locator(".q-checkbox", has_text="L3")).to_be_visible()

    # Reload page and verify everything persisted to SQLite cleanly.
    authed_page.reload()
    expect(authed_page.get_by_text("Cipher").first).to_be_visible()
    expect(authed_page.get_by_text("MCT 360 (Cyberdeck)")).to_be_visible()
    expect(authed_page.get_by_text("Aluminum Bone Lacing")).to_be_visible()
    expect(authed_page.get_by_text("5 / 6")).to_be_visible()
