"""
AI Helper Docstring
Purpose: NiceGUI view specifically guarded for roles of 'admin'. Generates massive aggrid-style list tables of active users.
Interactions:
- `app.api.user_routes` OR `app.services.user_service`: Makes physical fetches against the database async hooks to build table states.
"""

"""Admin user management page — /admin/users

Admin-only page with data table, create/edit/delete user dialogs,
and password reset functionality.

Calls the service layer directly (same process) rather than
going through the API via httpx.
"""

from nicegui import ui

from app.services.session import service_session
from app.user_roles import UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import (
    UserServiceError,
    create_user,
    delete_user,
    list_users,
    reset_password,
    update_user,
)
from app.ui.auth import current_user_context
from app.ui.theme import apply_global_styles, notify_error, notify_success
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar


@ui.page("/admin/users")
async def admin_users_page():
    """Admin user management page."""
    if current_user_context().role != UserRole.ADMIN:
        ui.navigate.to("/")
        return

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("User Management — DonjonDocs")

    build_header()
    build_sidebar()

    # State
    users_data = []

    # -----------------------------------------------------------------------
    # Data loading — direct service call
    # -----------------------------------------------------------------------
    async def load_users():
        nonlocal users_data
        async with service_session() as session:
            users_list, _total = await list_users(session, skip=0, limit=100)
            users_data = [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role.value,
                    "is_active": u.is_active,
                    "last_login": str(u.last_login) if u.last_login else "-",
                }
                for u in users_list
            ]
        users_table.refresh()

    # -----------------------------------------------------------------------
    # Create User Dialog
    # -----------------------------------------------------------------------
    def show_create_dialog():
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md").style(
            "background: #1E1E2E; border: 1px solid rgba(79, 70, 229, 0.2); border-radius: 12px;"
        ):
            ui.label("Create New User").classes("text-lg font-semibold mb-4").style("color: #E2E8F0;")

            c_username = ui.input(label="Username").classes("w-full").props("outlined dark")
            c_email = ui.input(label="Email").classes("w-full mt-2").props("outlined dark")
            c_password = ui.input(label="Password", password=True).classes("w-full mt-2").props("outlined dark")
            c_role = ui.select(
                label="Role",
                options=[r.value for r in UserRole],
                value=UserRole.STANDARD.value,
            ).classes("w-full mt-2").props("outlined dark")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def do_create():
                    async with service_session() as session:
                        try:
                            data = UserCreate(
                                username=c_username.value,
                                email=c_email.value,
                                password=c_password.value,
                                role=UserRole(c_role.value),
                            )
                            await create_user(session, data)
                            await session.commit()
                            notify_success("User created successfully")
                            dialog.close()
                            await load_users()
                        except UserServiceError as e:
                            notify_error(e.message)
                        except Exception as e:
                            notify_error(f"Creation failed: {e}")

                ui.button("Create", on_click=do_create, icon="person_add").props("unelevated").style(
                    "background: #4F46E5 !important; border-radius: 8px;"
                )

        dialog.open()

    # -----------------------------------------------------------------------
    # Edit User Dialog
    # -----------------------------------------------------------------------
    def show_edit_dialog(user: dict):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md").style(
            "background: #1E1E2E; border: 1px solid rgba(79, 70, 229, 0.2); border-radius: 12px;"
        ):
            ui.label(f"Edit User: {user['username']}").classes("text-lg font-semibold mb-4").style(
                "color: #E2E8F0;"
            )

            e_username = ui.input(label="Username", value=user["username"]).classes("w-full").props("outlined dark")
            e_email = ui.input(label="Email", value=user["email"]).classes("w-full mt-2").props("outlined dark")
            e_role = ui.select(
                label="Role",
                options=[r.value for r in UserRole],
                value=user["role"],
            ).classes("w-full mt-2").props("outlined dark")
            e_active = ui.switch("Active", value=user["is_active"]).classes("mt-2")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def do_save():
                    payload = {}
                    if e_username.value != user["username"]:
                        payload["username"] = e_username.value
                    if e_email.value != user["email"]:
                        payload["email"] = e_email.value
                    if e_role.value != user["role"]:
                        payload["role"] = e_role.value
                    if e_active.value != user["is_active"]:
                        payload["is_active"] = e_active.value

                    if not payload:
                        notify_error("No changes to save")
                        return

                    async with service_session() as session:
                        try:
                            data = UserUpdate(**payload)
                            await update_user(session, user["id"], data)
                            await session.commit()
                            notify_success("User updated successfully")
                            dialog.close()
                            await load_users()
                        except UserServiceError as e:
                            notify_error(e.message)
                        except Exception as e:
                            notify_error(f"Update failed: {e}")

                ui.button("Save", on_click=do_save, icon="save").props("unelevated").style(
                    "background: #4F46E5 !important; border-radius: 8px;"
                )

        dialog.open()

    # -----------------------------------------------------------------------
    # Reset Password Dialog
    # -----------------------------------------------------------------------
    def show_reset_password_dialog(user: dict):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm").style(
            "background: #1E1E2E; border: 1px solid rgba(79, 70, 229, 0.2); border-radius: 12px;"
        ):
            ui.label(f"Reset Password: {user['username']}").classes("text-lg font-semibold mb-4").style(
                "color: #E2E8F0;"
            )

            new_pw = ui.input(label="New Password", password=True).classes("w-full").props("outlined dark")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def do_reset():
                    if not new_pw.value or len(new_pw.value) < 8:
                        notify_error("Password must be at least 8 characters")
                        return

                    async with service_session() as session:
                        try:
                            await reset_password(session, user["id"], new_pw.value)
                            await session.commit()
                            notify_success("Password reset successfully")
                            dialog.close()
                        except UserServiceError as e:
                            notify_error(e.message)

                ui.button("Reset", on_click=do_reset, icon="lock_reset").props("unelevated").style(
                    "background: #EF4444 !important; border-radius: 8px;"
                )

        dialog.open()

    # -----------------------------------------------------------------------
    # Delete User Confirmation
    # -----------------------------------------------------------------------
    def show_delete_dialog(user: dict):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm").style(
            "background: #1E1E2E; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px;"
        ):
            ui.label("Deactivate User").classes("text-lg font-semibold mb-2").style("color: #EF4444;")
            ui.label(f"Are you sure you want to deactivate {user['username']}?").style("color: #E2E8F0;")
            ui.label("This can be reversed by editing the user.").classes("text-xs mt-1").style("color: #94A3B8;")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def do_delete():
                    async with service_session() as session:
                        try:
                            await delete_user(session, user["id"])
                            await session.commit()
                            notify_success("User deactivated")
                            dialog.close()
                            await load_users()
                        except UserServiceError as e:
                            notify_error(e.message)

                ui.button("Deactivate", on_click=do_delete, icon="person_off").props("unelevated").style(
                    "background: #EF4444 !important; border-radius: 8px;"
                )

        dialog.open()

    # -----------------------------------------------------------------------
    # Page Content
    # -----------------------------------------------------------------------
    with ui.column().classes("page-content"):
        with ui.row().classes("w-full items-center justify-between mb-6"):
            ui.label("User Management").classes("text-2xl font-bold").style("color: #E2E8F0;")
            ui.button(
                "Create User",
                on_click=show_create_dialog,
                icon="person_add",
            ).props("unelevated").style(
                "background: #4F46E5 !important; border-radius: 8px;"
            )

        # User table (refreshable)
        @ui.refreshable
        def users_table():
            if not users_data:
                ui.label("No users found. Create one to get started.").style("color: #94A3B8;")
                return

            columns = [
                {"name": "username", "label": "Username", "field": "username", "align": "left", "sortable": True},
                {"name": "email", "label": "Email", "field": "email", "align": "left", "sortable": True},
                {"name": "role", "label": "Role", "field": "role", "align": "center", "sortable": True},
                {"name": "is_active", "label": "Status", "field": "is_active", "align": "center"},
                {"name": "last_login", "label": "Last Login", "field": "last_login", "align": "center"},
                {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
            ]

            rows = []
            for u in users_data:
                rows.append({
                    "id": u["id"],
                    "username": u["username"],
                    "email": u["email"],
                    "role": u["role"],
                    "is_active": u["is_active"],
                    "last_login": u.get("last_login", "-") or "-",
                })

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
                pagination={"rowsPerPage": 20},
            ).classes("w-full").props("flat bordered dark")

            # Add slot for role badges and action buttons
            table.add_slot("body-cell-role", '''
                <q-td :props="props">
                    <q-badge :color="props.row.role === 'admin' ? 'red' : props.row.role === 'premium' ? 'amber' : 'green'"
                             :label="props.row.role" />
                </q-td>
            ''')

            table.add_slot("body-cell-is_active", '''
                <q-td :props="props">
                    <q-badge :color="props.row.is_active ? 'green' : 'grey'" :label="props.row.is_active ? 'Active' : 'Inactive'" />
                </q-td>
            ''')

            table.add_slot("body-cell-actions", r'''
                <q-td :props="props">
                    <q-btn flat round dense icon="edit" @click="$parent.$emit('edit', props.row)" size="sm" color="primary" />
                    <q-btn flat round dense icon="lock_reset" @click="$parent.$emit('reset', props.row)" size="sm" color="warning" />
                    <q-btn flat round dense icon="delete" @click="$parent.$emit('delete', props.row)" size="sm" color="negative" />
                </q-td>
            ''')

            def handle_edit(e):
                row = e.args
                user = next((u for u in users_data if u["id"] == row["id"]), None)
                if user:
                    show_edit_dialog(user)

            def handle_reset(e):
                row = e.args
                user = next((u for u in users_data if u["id"] == row["id"]), None)
                if user:
                    show_reset_password_dialog(user)

            def handle_delete(e):
                row = e.args
                user = next((u for u in users_data if u["id"] == row["id"]), None)
                if user:
                    show_delete_dialog(user)

            table.on("edit", handle_edit)
            table.on("reset", handle_reset)
            table.on("delete", handle_delete)

        users_table()

    # Load data on page load
    await load_users()
