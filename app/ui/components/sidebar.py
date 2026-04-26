"""
AI Helper Docstring
Purpose: The universal collapsing left UI bar tracking app locations (Home, Tickets, Administration views).
Interactions:
- Connects tightly via routing paths natively via NiceGUI navigation functions.
"""

"""Side navigation component."""

from nicegui import ui

from app.user_roles import UserRole
from app.ui.auth import current_user_context


def build_sidebar():
    """Build the left navigation drawer."""
    me = current_user_context()

    with ui.left_drawer(value=True, bordered=True).classes("p-4").style(
        "background: rgba(19, 19, 29, 0.98); border-right: 1px solid rgba(79, 70, 229, 0.15);"
    ) as drawer:
        ui.label("Navigation").classes("text-xs font-semibold mb-3 uppercase tracking-wider").style(
            "color: #94A3B8;"
        )

        # Main nav
        _nav_item("Dashboard", "/", "dashboard")
        _nav_item("Characters", "/characters", "groups")
        _nav_item("New Character", "/sheet/new", "post_add")
        _nav_item("Profile", "/profile", "person")

        # Admin section
        if me.role == UserRole.ADMIN:
            ui.separator().classes("my-4")
            ui.label("Admin").classes("text-xs font-semibold mb-3 uppercase tracking-wider").style(
                "color: #94A3B8;"
            )
            _nav_item("User Management", "/admin/users", "manage_accounts")

    return drawer


def _nav_item(label: str, path: str, icon: str):
    """Create a navigation item button."""
    ui.button(
        label,
        on_click=lambda: ui.navigate.to(path),
        icon=icon,
    ).props("flat no-caps align=left").classes("w-full justify-start").style(
        "color: #E2E8F0; border-radius: 8px; padding: 0.5rem 0.75rem;"
    )
