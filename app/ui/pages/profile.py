"""
AI Helper Docstring
Purpose: NiceGUI view granting standard and premium users the ability to perform basic profile edits. Identity comes from middleware-populated UserContext; mutating calls run in the browser so the HttpOnly access_token cookie authorizes them natively.
Interactions:
- Reads identity via `current_user_context()`. PUT /api/users/me and POST /api/users/me/change-password are invoked via browser fetch (`ui.run_javascript`), not a server-side httpx hop.
"""

"""Profile page — /profile

Self-service profile management: view account info, change username/email, change password.
No role changes allowed.
"""

import json

from nicegui import ui

from app.ui.auth import current_user_context
from app.ui.theme import apply_global_styles, notify_error, notify_success, role_badge_html
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar


@ui.page("/profile")
async def profile_page():
    """Profile management page."""
    me = current_user_context()

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("Profile — DonjonDocs")

    build_header()
    build_sidebar()

    with ui.column().classes("page-content"):
        ui.label("Profile Settings").classes("text-2xl font-bold mb-6").style(
            "color: #E2E8F0;"
        )

        with ui.row().classes("w-full gap-6 flex-wrap"):
            # Left column: Account info + edit profile
            with ui.column().classes("flex-1 min-w-[350px] gap-4"):
                # Account Info
                with ui.card().classes("stat-card w-full"):
                    ui.label("Account Information").classes(
                        "text-sm font-semibold uppercase tracking-wider mb-4"
                    ).style("color: #94A3B8;")

                    with ui.column().classes("gap-3"):
                        _info_row("Username", me.username)
                        _info_row("Email", me.email)
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Role").classes("text-sm").style("color: #94A3B8; min-width: 100px;")
                            ui.html(role_badge_html(me.role.value))

                # Edit Profile
                with ui.card().classes("stat-card w-full"):
                    ui.label("Edit Profile").classes(
                        "text-sm font-semibold uppercase tracking-wider mb-4"
                    ).style("color: #94A3B8;")

                    edit_username = ui.input(
                        label="Username",
                        value=me.username,
                    ).classes("w-full").props('outlined dark')

                    edit_email = ui.input(
                        label="Email",
                        value=me.email,
                    ).classes("w-full mt-2").props('outlined dark')

                    async def handle_update_profile():
                        payload = {}
                        if edit_username.value != me.username:
                            payload["username"] = edit_username.value
                        if edit_email.value != me.email:
                            payload["email"] = edit_email.value

                        if not payload:
                            notify_error("No changes to save")
                            return

                        body = json.dumps(payload)
                        result = await ui.run_javascript(f"""
                            (async () => {{
                                try {{
                                    const resp = await fetch('/api/users/me', {{
                                        method: 'PUT',
                                        headers: {{'Content-Type': 'application/json'}},
                                        body: {json.dumps(body)},
                                        credentials: 'same-origin',
                                    }});
                                    if (resp.ok) return {{ok: true}};
                                    const data = await resp.json().catch(() => ({{}}));
                                    return {{ok: false, detail: data.detail || 'Update failed'}};
                                }} catch (err) {{
                                    return {{ok: false, detail: 'Network error: ' + err.message}};
                                }}
                            }})()
                        """, timeout=10)

                        if result and result.get("ok"):
                            notify_success("Profile updated successfully")
                            # Re-nav to refresh the middleware-sourced UserContext.
                            ui.navigate.to("/profile")
                        else:
                            notify_error((result or {}).get("detail", "Update failed"))

                    ui.button(
                        "Save Changes",
                        on_click=handle_update_profile,
                        icon="save",
                    ).classes("mt-3").props("unelevated").style(
                        "background: #4F46E5 !important; border-radius: 8px;"
                    )

            # Right column: Change password
            with ui.column().classes("flex-1 min-w-[350px] gap-4"):
                with ui.card().classes("stat-card w-full"):
                    ui.label("Change Password").classes(
                        "text-sm font-semibold uppercase tracking-wider mb-4"
                    ).style("color: #94A3B8;")

                    current_pw = ui.input(
                        label="Current Password",
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full").props('outlined dark')

                    new_pw = ui.input(
                        label="New Password",
                        password=True,
                        password_toggle_button=True,
                        validation={"Min 8 characters": lambda v: len(v) >= 8 if v else False},
                    ).classes("w-full mt-2").props('outlined dark')

                    confirm_pw = ui.input(
                        label="Confirm New Password",
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full mt-2").props('outlined dark')

                    async def handle_change_password():
                        if not all([current_pw.value, new_pw.value, confirm_pw.value]):
                            notify_error("Please fill in all password fields")
                            return
                        if new_pw.value != confirm_pw.value:
                            notify_error("New passwords do not match")
                            return
                        if len(new_pw.value) < 8:
                            notify_error("Password must be at least 8 characters")
                            return

                        body = json.dumps({
                            "current_password": current_pw.value,
                            "new_password": new_pw.value,
                        })
                        result = await ui.run_javascript(f"""
                            (async () => {{
                                try {{
                                    const resp = await fetch('/api/users/me/change-password', {{
                                        method: 'POST',
                                        headers: {{'Content-Type': 'application/json'}},
                                        body: {json.dumps(body)},
                                        credentials: 'same-origin',
                                    }});
                                    if (resp.ok) return {{ok: true}};
                                    const data = await resp.json().catch(() => ({{}}));
                                    return {{ok: false, detail: data.detail || 'Password change failed'}};
                                }} catch (err) {{
                                    return {{ok: false, detail: 'Network error: ' + err.message}};
                                }}
                            }})()
                        """, timeout=10)

                        if result and result.get("ok"):
                            notify_success("Password changed successfully")
                            current_pw.value = ""
                            new_pw.value = ""
                            confirm_pw.value = ""
                        else:
                            notify_error((result or {}).get("detail", "Password change failed"))

                    ui.button(
                        "Change Password",
                        on_click=handle_change_password,
                        icon="lock",
                    ).classes("mt-3").props("unelevated").style(
                        "background: #4F46E5 !important; border-radius: 8px;"
                    )


def _info_row(label: str, value: str):
    """Display an info row with label and value."""
    with ui.row().classes("items-center gap-2"):
        ui.label(label).classes("text-sm").style("color: #94A3B8; min-width: 100px;")
        ui.label(value).classes("text-sm font-medium").style("color: #E2E8F0;")
