"""
AI Helper Docstring
Purpose: The universal top level UI bar rendering app titles and User drop-down menus (Logout, Settings).
Interactions:
- `app.ui.pages.*`: Hooked immediately onto Dashboard, Admin panels, etc for navigation.
"""

"""Top navigation header component."""

from nicegui import app, ui

from app.config import get_settings
from app.user_roles import UserRole
from app.ui.auth import current_user_context


def build_header():
    """Build the top navigation bar."""
    settings = get_settings()
    me = current_user_context()

    with ui.header().classes("items-center justify-between px-6 py-2").style(
        "background: rgba(19, 19, 29, 0.95); backdrop-filter: blur(10px); "
        "border-bottom: 1px solid rgba(79, 70, 229, 0.2);"
    ):
        # Left: App name
        with ui.row().classes("items-center gap-3 cursor-pointer no-wrap"):
            ui.icon("shield", size="sm").style("color: #4F46E5;")
            ui.label(settings.APP_NAME).classes("text-lg font-semibold").style(
                "color: #E2E8F0; letter-spacing: -0.025em;"
            )

        # Center: Nav links
        with ui.row().classes("items-center gap-1 max-[768px]:hidden"):
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/"), icon="dashboard").props(
                "flat no-caps"
            ).style("color: #94A3B8;")

            if me.role == UserRole.ADMIN:
                ui.button("Admin Panel", on_click=lambda: ui.navigate.to("/admin/users"), icon="admin_panel_settings").props(
                    "flat no-caps"
                ).style("color: #94A3B8;")

        # Right: User menu
        with ui.row().classes("items-center gap-2"):
            username = me.username
            role = me.role.value

            with ui.button(icon="account_circle").props("flat round").style("color: #94A3B8;"):
                with ui.menu().props("auto-close"):
                    with ui.column().classes("p-3 gap-1"):
                        ui.label(username).classes("font-semibold").style("color: #E2E8F0;")
                        ui.label(role.upper()).classes("text-xs").style(
                            f"color: {'#EF4444' if role == 'admin' else '#F59E0B' if role == 'premium' else '#10B981'};"
                        )
                    ui.separator()
                    ui.menu_item(
                        "Profile",
                        on_click=lambda: ui.navigate.to("/profile"),
                    ).props("dense")
                    async def _handle_logout():
                        # POST via browser fetch so the browser receives the
                        # HttpOnly Set-Cookie deletion without exposing a
                        # state-changing GET logout endpoint (CSRF hardening).
                        await ui.run_javascript(
                            "fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'}).catch(() => {})",
                            timeout=5,
                        )
                        app.storage.user.clear()
                        ui.navigate.to("/login")

                    ui.menu_item(
                        "Logout",
                        on_click=_handle_logout,
                    ).props("dense")
