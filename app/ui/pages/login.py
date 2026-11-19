"""
AI Helper Docstring
Purpose: NiceGUI view holding authentication forms. Submits credentials directly from the browser to `/api/auth/login` via `fetch`, so the API response sets the HttpOnly `access_token` cookie natively.
Interactions:
- `app.api.auth_routes.login`: browser POSTs JSON; on success the HttpOnly cookie is set and subsequent navigations carry it to AuthMiddleware.
"""

"""Login page — /login

Centered glassmorphism card with email + password fields. The submit
handler runs a browser-side fetch against `/api/auth/login` so the
HttpOnly `access_token` cookie is set on the browser directly. No
token is written into `app.storage.user`.
"""

import json

from nicegui import context, ui

from app.config import get_settings
from app.ui.auth import sanitize_redirect_target
from app.ui.theme import apply_auth_background, apply_global_styles, notify_error


@ui.page("/login")
async def login_page(redirect_to: str = "/"):
    """Login page with email and password authentication."""
    settings = get_settings()
    safe_redirect = sanitize_redirect_target(redirect_to)

    # Already authenticated? The AuthMiddleware skips /login, so we have
    # to check the cookie ourselves to avoid showing the form to a
    # logged-in user navigating back.
    request = context.client.request
    if request is not None and request.cookies.get("access_token"):
        ui.navigate.to(safe_redirect)
        return

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title(f"Login — {settings.APP_NAME}")

    apply_auth_background()

    with ui.column().classes("auth-bg items-center justify-center w-full"):
        with ui.card().classes("auth-card"):
            # Logo / Title
            with ui.column().classes("items-center mb-6 gap-2"):
                ui.icon("shield", size="xl").style("color: #4F46E5;")
                ui.label(settings.APP_NAME).classes("text-2xl font-bold").style(
                    "color: #E2E8F0; letter-spacing: -0.025em;"
                )
                ui.label("Sign in to your account").classes("text-sm").style(
                    "color: #94A3B8;"
                )

            # Form fields
            email = ui.input(
                label="Email",
                placeholder="you@example.com",
                validation={"Required": lambda v: bool(v)},
            ).classes("w-full").props('outlined standout="bg-indigo-900" dark')

            password = ui.input(
                label="Password",
                password=True,
                password_toggle_button=True,
                validation={"Required": lambda v: bool(v)},
            ).classes("w-full mt-2").props('outlined standout="bg-indigo-900" dark')

            async def handle_login():
                if not email.value or not password.value:
                    notify_error("Please fill in all fields")
                    return

                body = json.dumps({"email": email.value, "password": password.value})
                result = await ui.run_javascript(f"""
                    (async () => {{
                        try {{
                            const resp = await fetch('/api/auth/login', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: {json.dumps(body)},
                                credentials: 'same-origin',
                            }});
                            if (resp.ok) return {{ok: true}};
                            const data = await resp.json().catch(() => ({{}}));
                            return {{ok: false, detail: data.detail || 'Login failed'}};
                        }} catch (err) {{
                            return {{ok: false, detail: 'Network error: ' + err.message}};
                        }}
                    }})()
                """, timeout=10)

                if result and result.get("ok"):
                    ui.navigate.to(safe_redirect)
                else:
                    notify_error((result or {}).get("detail", "Login failed"))

            # Login button
            ui.button(
                "Sign In",
                on_click=handle_login,
                icon="login",
            ).classes("w-full mt-4").props('unelevated size=lg').style(
                "background: #4F46E5 !important; border-radius: 10px;"
            )

            # Enter key support
            password.on("keydown.enter", handle_login)
            email.on("keydown.enter", lambda: password.run_method("focus"))

            # Register link
            if settings.ALLOW_REGISTRATION:
                with ui.row().classes("w-full justify-center mt-5"):
                    ui.label("Don't have an account?").style("color: #94A3B8;")
                    ui.link("Register", "/register").style(
                        "color: #818CF8; font-weight: 500;"
                    )
