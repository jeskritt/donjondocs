"""
AI Helper Docstring
Purpose: Semantic Quasar / NiceGUI Playwright helpers for E2E tests. Avoids
brittle NiceGUI auto-generated DOM IDs (`#c12` / `#ng-12`) so the same tests
work identically across NiceGUI 3.x and NiceGUI 4.x.
Interactions:
- Consumed by `tests/e2e/test_*.py`.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect


def active_dialog(page: Page) -> Locator:
    """Return the topmost visible Quasar dialog card."""
    dlg = page.locator(".q-dialog .q-card").last
    expect(dlg).to_be_visible()
    return dlg


def sheet_card(page: Page, heading: str) -> Locator:
    """Locate a character-sheet `.q-card` by its header title label."""
    return page.locator(".q-card").filter(
        has=page.locator(".text-xl", has_text=re.compile(rf"^{re.escape(heading)}$"))
    ).first


def icon_button(scope: Locator | Page, icon_name: str) -> Locator:
    """Locate a Quasar button by its Material icon ligature text (e.g. 'edit')."""
    root = scope if isinstance(scope, Page) else scope.page
    return scope.locator("button").filter(
        has=root.locator("i.q-icon", has_text=re.compile(rf"^{re.escape(icon_name)}$"))
    )


def select_quasar_option(
    page: Page,
    scope: Locator | Page,
    label: str,
    option_text: str,
    *,
    filterable: bool = False,
) -> None:
    """Pick `option_text` from a Quasar `ui.select` identified by its label.

    Uses Quasar's `.q-field` wrapper around the label so it works whether or
    not `with_input=True` is set on the select.
    """
    field = scope.locator(".q-select").filter(
        has=page.locator(".q-field__label", has_text=re.compile(rf"^{re.escape(label)}$"))
    ).first
    field.click()

    if filterable:
        search_inp = field.locator("input").first
        search_inp.fill(option_text)

    menu = page.locator(".q-menu").last
    expect(menu).to_be_visible()
    menu.locator(".q-item").filter(
        has_text=re.compile(rf"^{re.escape(option_text)}$")
    ).first.click()
    expect(menu).to_be_hidden()


def fill_field(scope: Locator | Page, label: str, value: str) -> None:
    """Fill a Quasar input/number/textarea inside `scope` matched by exact label."""
    root = scope if isinstance(scope, Page) else scope.page
    field = scope.locator("label.q-field").filter(
        has=root.locator(".q-field__label", has_text=re.compile(rf"^{re.escape(label)}$"))
    ).first
    inp = field.locator("input, textarea").first
    inp.fill(value)


def set_checkbox(scope: Locator | Page, label: str, checked: bool) -> None:
    """Set a labelled Quasar checkbox to `checked`."""
    box = scope.locator(".q-checkbox").filter(
        has_text=re.compile(rf"^{re.escape(label)}$")
    ).first
    is_checked = box.get_attribute("aria-checked") == "true"
    if is_checked != checked:
        box.click()
    expect(box).to_have_attribute("aria-checked", "true" if checked else "false")


def click_and_wait_refresh(page: Page, target: Locator) -> None:
    """Click a control that triggers a NiceGUI `@ui.refreshable` `_save` rebuild,
    waiting until the clicked DOM node is detached by the server re-render.

    Eliminates races where a subsequent click lands just before the previous
    `_save` finishes refreshing sibling cards.
    """
    handle = target.element_handle()
    assert handle is not None
    target.click()
    page.wait_for_function("el => !el.isConnected", arg=handle)


def wait_saved_toast(page: Page, text: str = "Saved") -> None:
    """Wait briefly for a NiceGUI notification matching `text`."""
    expect(page.locator(".q-notification", has_text=text).last).to_be_visible()
