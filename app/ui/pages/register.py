"""
AI Helper Docstring
Purpose: NiceGUI form strictly validating password rules, then submitting directly from the browser to `/api/auth/register`.
Interactions:
- Mirrors `login.py` — the browser POSTs JSON to the API; on success the HttpOnly cookie is set and AuthMiddleware picks it up on the next navigation.
"""

"""Register page — /register

Only available when ALLOW_REGISTRATION=true. The submit handler runs a
browser-side fetch against `/api/auth/register` so the API response
sets the HttpOnly `access_token` cookie directly.
"""

import json

from nicegui import context, ui

from app.config import get_settings
from app.ui.theme import apply_auth_background, apply_global_styles, notify_error


@ui.page("/register")
async def register_page():
    """Registration page with username, email, and password fields."""
    settings = get_settings()

    # Gate registration
    if not settings.ALLOW_REGISTRATION:
        ui.navigate.to("/login")
        return

    # If already authenticated, redirect to dashboard
    request = context.client.request
    if request is not None and request.cookies.get("access_token"):
        ui.navigate.to("/")
        return

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title(f"Register — {settings.APP_NAME}")

    apply_auth_background()

    with ui.column().classes("auth-bg items-center justify-center w-full"):
        with ui.card().classes("auth-card"):
            # Logo / Title
            with ui.column().classes("items-center mb-6 gap-2"):
                ui.icon("shield", size="xl").style("color: #4F46E5;")
                ui.label(settings.APP_NAME).classes("text-2xl font-bold").style(
                    "color: #E2E8F0; letter-spacing: -0.025em;"
                )
                ui.label("Create your account").classes("text-sm").style(
                    "color: #94A3B8;"
                )

            # Form fields
            username = ui.input(
                label="Username",
                placeholder="johndoe",
                validation={
                    "Min 3 characters": lambda v: len(v) >= 3 if v else False,
                    "Letters, numbers, _ and - only": lambda v: all(
                        c.isalnum() or c in "_-" for c in v
                    ) if v else True,
                },
            ).classes("w-full").props('outlined standout="bg-indigo-900" dark')

            email = ui.input(
                label="Email",
                placeholder="you@example.com",
                validation={"Required": lambda v: bool(v)},
            ).classes("w-full mt-2").props('outlined standout="bg-indigo-900" dark')

            password = ui.input(
                label="Password",
                password=True,
                password_toggle_button=True,
                validation={"Min 8 characters": lambda v: len(v) >= 8 if v else False},
            ).classes("w-full mt-2").props('outlined standout="bg-indigo-900" dark')

            confirm_password = ui.input(
                label="Confirm Password",
                password=True,
                password_toggle_button=True,
                validation={"Required": lambda v: bool(v)},
            ).classes("w-full mt-2").props('outlined standout="bg-indigo-900" dark')

            async def handle_register():
                if not all([username.value, email.value, password.value, confirm_password.value]):
                    notify_error("Please fill in all fields")
                    return

                if password.value != confirm_password.value:
                    notify_error("Passwords do not match")
                    return

                if len(password.value) < 8:
                    notify_error("Password must be at least 8 characters")
                    return

                body = json.dumps({
                    "username": username.value,
                    "email": email.value,
                    "password": password.value,
                })
                result = await ui.run_javascript(f"""
                    (async () => {{
                        try {{
                            const resp = await fetch('/api/auth/register', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: {json.dumps(body)},
                                credentials: 'same-origin',
                            }});
                            if (resp.ok) return {{ok: true}};
                            const data = await resp.json().catch(() => ({{}}));
                            return {{ok: false, detail: data.detail || 'Registration failed'}};
                        }} catch (err) {{
                            return {{ok: false, detail: 'Network error: ' + err.message}};
                        }}
                    }})()
                """, timeout=10)

                if result and result.get("ok"):
                    ui.navigate.to("/")
                else:
                    notify_error((result or {}).get("detail", "Registration failed"))

            # Register button
            ui.button(
                "Create Account",
                on_click=handle_register,
                icon="person_add",
            ).classes("w-full mt-4").props('unelevated size=lg').style(
                "background: #4F46E5 !important; border-radius: 10px;"
            )

            confirm_password.on("keydown.enter", handle_register)

            # Login link
            with ui.row().classes("w-full justify-center mt-5"):
                ui.label("Already have an account?").style("color: #94A3B8;")
                ui.link("Sign In", "/login").style(
                    "color: #818CF8; font-weight: 500;"
                )
