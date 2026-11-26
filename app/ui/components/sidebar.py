"""
AI Helper Docstring
Purpose: The universal collapsing left UI bar tracking app locations (Home, Tickets, Administration views). Quasar drawer in mini-mode hides labels and shrinks to icons-only; the user's collapse preference persists in `app.storage.user["sidebar_collapsed"]`.
Interactions:
- Connects tightly via routing paths natively via NiceGUI navigation functions.
- Reads/writes `app.storage.user["sidebar_collapsed"]` for the collapse state (same per-user storage as `phb_style`; never enters character_data).
"""

"""Side navigation component."""

from nicegui import app, ui

from app.user_roles import UserRole
from app.ui.auth import current_user_context


def build_sidebar():
    """Build the left navigation drawer.

    The drawer renders in Quasar mini-mode when
    `app.storage.user["sidebar_collapsed"]` is True: width collapses to ~56px,
    icons remain visible, labels hide. Toggle button at the top flips the
    preference and re-renders the drawer body in place.
    """
    me = current_user_context()
    collapsed = bool(app.storage.user.get("sidebar_collapsed", False))

    # Mini-mode width tuned so each icon button still centres cleanly. The
    # `mini` prop alone collapses the drawer; we also set the width prop so
    # the parchment-light Material icons sit comfortably.
    drawer_props = "bordered"
    if collapsed:
        drawer_props += " mini mini-to-overlay=false width=56"
    with ui.left_drawer(value=True).props(drawer_props).classes("p-2").style(
        "background: rgba(19, 19, 29, 0.98); border-right: 1px solid rgba(79, 70, 229, 0.15);"
    ) as drawer:
        # Toggle button — chevron flips with state.
        toggle_icon = "chevron_right" if collapsed else "chevron_left"

        def _toggle_sidebar():
            app.storage.user["sidebar_collapsed"] = not bool(
                app.storage.user.get("sidebar_collapsed", False)
            )
            ui.navigate.reload()  # cleanest way to re-render with new Quasar props

        ui.button(
            icon=toggle_icon,
            on_click=_toggle_sidebar,
        ).props("flat round dense").classes("ml-auto mb-2").style("color: #94A3B8;")

        if not collapsed:
            ui.label("Navigation").classes("text-xs font-semibold mb-3 uppercase tracking-wider").style(
                "color: #94A3B8;"
            )

        # Main nav. Order matters — Creatures sits under Characters per spec.
        _nav_item("Dashboard", "/", "dashboard", collapsed)
        _nav_item("Characters", "/characters", "groups", collapsed)
        _nav_item("Creatures", "/creatures", "pets", collapsed)
        _nav_item("New Character", "/sheet/new", "post_add", collapsed)
        _nav_item("Profile", "/profile", "person", collapsed)

        # Admin section
        if me.role == UserRole.ADMIN:
            ui.separator().classes("my-4")
            if not collapsed:
                ui.label("Admin").classes("text-xs font-semibold mb-3 uppercase tracking-wider").style(
                    "color: #94A3B8;"
                )
            _nav_item("Admin Panel", "/admin/users", "admin_panel_settings", collapsed)

    return drawer


def _nav_item(label: str, path: str, icon: str, collapsed: bool):
    """Create a navigation item button. In collapsed mode the label is hidden
    and the icon centres in the narrow drawer."""
    btn_label = "" if collapsed else label
    btn = ui.button(
        btn_label,
        on_click=lambda: ui.navigate.to(path),
        icon=icon,
    ).props("flat no-caps align=left").classes(
        "w-full justify-center" if collapsed else "w-full justify-start"
    ).style(
        "color: #E2E8F0; border-radius: 8px; padding: 0.5rem 0.5rem;"
    )
    if collapsed:
        # When the label is empty Quasar still shows a tooltip on hover.
        btn.tooltip(label)
