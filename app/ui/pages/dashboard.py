"""
AI Helper Docstring
Purpose: Default Landing view (`/`) following a successful auth attempt. Shows metrics, role overviews, and system checks.
Interactions:
- `app.ui.components.*`: Leverages standard wrappers. Reads identity via `current_user_context()` (middleware-populated).
"""

"""Dashboard page — /

Landing page after login. Shows user greeting, role badge, and quick stats.
"""

from nicegui import ui

from app.user_roles import UserRole
from app.ui.auth import current_user_context
from app.ui.theme import apply_global_styles, role_badge_html
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar


@ui.page("/")
async def dashboard_page():
    """Main dashboard page — authenticated users only."""
    me = current_user_context()

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("Dashboard — DonjonDocs")

    build_header()
    build_sidebar()

    # Content area
    with ui.column().classes("page-content"):
        # Welcome section
        with ui.row().classes("items-center gap-3 mb-6"):
            ui.label(f"Welcome back, {me.username}").classes(
                "text-3xl font-bold"
            ).style("color: #E2E8F0;")
            ui.html(role_badge_html(me.role.value))

        ui.label("Your workspace at a glance").classes("text-sm mb-6").style(
            "color: #94A3B8;"
        )

        # Stats cards
        with ui.row().classes("w-full gap-4 flex-wrap"):
            # Role card
            with ui.card().classes("stat-card flex-1 min-w-[250px]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("verified_user", size="md").style("color: #4F46E5;")
                    with ui.column().classes("gap-0"):
                        ui.label("Account Role").classes("text-xs font-semibold uppercase tracking-wider").style(
                            "color: #94A3B8;"
                        )
                        ui.label(me.role.value.title()).classes(
                            "text-xl font-bold"
                        ).style("color: #E2E8F0;")

            # Status card
            with ui.card().classes("stat-card flex-1 min-w-[250px]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("check_circle", size="md").style("color: #10B981;")
                    with ui.column().classes("gap-0"):
                        ui.label("Account Status").classes("text-xs font-semibold uppercase tracking-wider").style(
                            "color: #94A3B8;"
                        )
                        ui.label("Active").classes("text-xl font-bold").style(
                            "color: #E2E8F0;"
                        )

            # Quick action card
            with ui.card().classes("stat-card flex-1 min-w-[250px]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("settings", size="md").style("color: #F59E0B;")
                    with ui.column().classes("gap-0"):
                        ui.label("Quick Actions").classes("text-xs font-semibold uppercase tracking-wider").style(
                            "color: #94A3B8;"
                        )
                        ui.button(
                            "Edit Profile",
                            on_click=lambda: ui.navigate.to("/profile"),
                            icon="edit",
                        ).props("flat no-caps dense").style("color: #818CF8;")

        # Characters section
        ui.separator().classes("my-6")
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.icon("group", size="sm").style("color: #A855F7;")
            ui.label("Characters").classes("text-lg font-semibold").style("color: #E2E8F0;")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            with ui.card().classes("stat-card flex-1 min-w-[250px]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("library_books", size="md").style("color: #A855F7;")
                    with ui.column().classes("gap-0"):
                        ui.label("My Characters").classes("text-xs font-semibold uppercase tracking-wider").style("color: #94A3B8;")
                        ui.button("View All", on_click=lambda: ui.navigate.to("/characters")).props("flat no-caps dense").style("color: #E2E8F0;")

            with ui.card().classes("stat-card flex-1 min-w-[250px]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("add_circle", size="md").style("color: #10B981;")
                    with ui.column().classes("gap-0"):
                        ui.label("Create").classes("text-xs font-semibold uppercase tracking-wider").style("color: #94A3B8;")
                        ui.button("New Sheet", on_click=lambda: ui.navigate.to("/sheet/new")).props("flat no-caps dense").style("color: #E2E8F0;")

        # Admin section
        if me.role == UserRole.ADMIN:
            ui.separator().classes("my-6")
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("admin_panel_settings", size="sm").style("color: #EF4444;")
                ui.label("Admin Panel").classes("text-lg font-semibold").style(
                    "color: #E2E8F0;"
                )

            with ui.card().classes("stat-card"):
                ui.button(
                    "Open Admin Panel",
                    on_click=lambda: ui.navigate.to("/admin/users"),
                    icon="admin_panel_settings",
                ).props("flat no-caps").style("color: #818CF8;")
