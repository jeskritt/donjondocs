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
from app.services.admin_service import (
    AdminServiceError,
    create_verified_admin_backup,
    get_global_table_stats,
    reseed_global_data,
)
from app.services.user_service import (
    UserServiceError,
    create_user,
    delete_user,
    list_users,
    reset_password,
    update_user,
)
from app.ui.auth import current_user_context
from app.ui.theme import DIALOG_CARD_STYLE, apply_global_styles, notify_error, notify_success
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
    me = current_user_context()
    users_data = []
    global_stats_data: list[dict] = []

    async def load_global_stats():
        nonlocal global_stats_data
        async with service_session() as session:
            global_stats_data = await get_global_table_stats(session, me)
        global_stats_table.refresh()

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

        # -------------------------------------------------------------------
        # System & Rule Data Management (Reseed + Guardrailed Backup)
        # -------------------------------------------------------------------
        ui.separator().classes("my-8")
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-3 mb-4"):
            with ui.column().classes("gap-0"):
                ui.label("Rule Data & Database Backup").classes("text-2xl font-bold").style("color: #E2E8F0;")
                ui.label("Reseed bundled rulebook tables from data/ or export a password-verified backup.").classes("text-xs text-gray-400")
            with ui.row().classes("gap-2"):
                def show_reseed_dialog():
                    with ui.dialog().props("persistent") as dlg, ui.card().classes("w-full max-w-md").style(DIALOG_CARD_STYLE):
                        ui.label("Reseed Global Rule Data").classes("text-lg font-bold text-white mb-2")
                        ui.label(
                            "Re-ingests bundled CSV and JSON rule catalogs from the server's data/ directory "
                            "using idempotent upserts. User accounts, characters, creatures, and user-owned custom "
                            "items are never modified."
                        ).classes("text-sm text-gray-300")

                        progress_box = ui.column().classes("w-full gap-2 mt-4")
                        progress_box.set_visibility(False)
                        with progress_box:
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.spinner("dots", size="sm", color="indigo")
                                status_lbl = ui.label("Preparing reseed…").classes("text-xs text-indigo-200")
                            progress_bar = ui.linear_progress(value=0.0, show_value=False).props(
                                "color=indigo rounded size=8px"
                            ).classes("w-full")

                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            cancel_btn = ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                            reseed_btn = ui.button("Reseed Now", icon="sync").props("unelevated color=primary")

                            def _on_progress(completed: int, total: int, label: str, rep: dict):
                                pct = (completed / total) if total > 0 else 1.0
                                progress_bar.set_value(pct)
                                status_lbl.set_text(
                                    f"({completed}/{total}) {label}  [+{rep['inserted']} / ~{rep['updated']}]"
                                )

                            async def _do_reseed():
                                cancel_btn.disable()
                                reseed_btn.disable()
                                reseed_btn.props("loading")
                                status_lbl.set_text("Starting reseed…")
                                progress_bar.set_value(0.0)
                                progress_box.set_visibility(True)
                                try:
                                    async with service_session() as session:
                                        report = await reseed_global_data(
                                            session, me, on_progress=_on_progress
                                        )
                                except AdminServiceError as exc:
                                    notify_error(exc.message)
                                    progress_box.set_visibility(False)
                                    reseed_btn.props(remove="loading")
                                    reseed_btn.enable()
                                    cancel_btn.enable()
                                    return
                                except Exception as exc:
                                    notify_error(f"Reseed failed: {exc}")
                                    progress_box.set_visibility(False)
                                    reseed_btn.props(remove="loading")
                                    reseed_btn.enable()
                                    cancel_btn.enable()
                                    return
                                notify_success(
                                    f"Reseeded {report['files']} files "
                                    f"(+{report['inserted']} inserted, ~{report['updated']} updated)."
                                )
                                dlg.close()
                                await load_global_stats()

                            reseed_btn.on_click(_do_reseed)
                    dlg.open()

                def show_backup_dialog():
                    with ui.dialog().props("persistent") as dlg, ui.card().classes("w-full max-w-md").style(DIALOG_CARD_STYLE):
                        ui.label("Download Database Backup").classes("text-lg font-bold text-white mb-1")
                        ui.label(
                            "Exports all users, characters, allies, notes, creatures, and custom global items as JSON. "
                            "Re-enter your admin password to authorize this download (max 2/hour; restore remains CLI-only)."
                        ).classes("text-xs text-gray-300 mb-3")
                        pw_in = ui.input(label="Confirm Admin Password", password=True).props("outlined dark dense").classes("w-full")
                        exclude_pw = ui.checkbox(
                            "Exclude password hashes (recommended — reset passwords after restore)",
                            value=True,
                        ).classes("mt-2 text-xs text-gray-200")

                        busy_row = ui.row().classes("w-full items-center gap-2 mt-3")
                        busy_row.set_visibility(False)
                        with busy_row:
                            ui.spinner("dots", size="sm", color="teal")
                            ui.label("Verifying password and generating backup…").classes("text-xs text-teal-200")

                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            cancel_btn = ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                            backup_btn = ui.button("Download Backup", icon="download").props("unelevated").style(
                                "background: #0F766E !important; border-radius: 8px;"
                            )

                            def _reset_controls():
                                busy_row.set_visibility(False)
                                backup_btn.props(remove="loading")
                                backup_btn.enable()
                                cancel_btn.enable()
                                pw_in.enable()
                                exclude_pw.enable()

                            async def _do_backup():
                                cancel_btn.disable()
                                backup_btn.disable()
                                backup_btn.props("loading")
                                pw_in.disable()
                                exclude_pw.disable()
                                busy_row.set_visibility(True)
                                try:
                                    async with service_session() as session:
                                        filename, payload, summary = await create_verified_admin_backup(
                                            session,
                                            me,
                                            pw_in.value or "",
                                            include_passwords=not bool(exclude_pw.value),
                                        )
                                except AdminServiceError as exc:
                                    notify_error(exc.message)
                                    _reset_controls()
                                    return
                                except Exception as exc:
                                    notify_error(f"Backup failed: {exc}")
                                    _reset_controls()
                                    return
                                ui.download(payload, filename=filename)
                                notify_success(
                                    f"Backup ready ({summary['users']} users, {summary['characters']} chars, "
                                    f"{summary['creatures']} creatures)."
                                )
                                dlg.close()

                            backup_btn.on_click(_do_backup)
                    dlg.open()

                ui.button(
                    "Reseed Global Data",
                    on_click=show_reseed_dialog,
                    icon="sync",
                ).props("unelevated").style(
                    "background: #4F46E5 !important; border-radius: 8px;"
                )
                ui.button(
                    "Download Backup",
                    on_click=show_backup_dialog,
                    icon="download",
                ).props("unelevated").style(
                    "background: #0F766E !important; border-radius: 8px;"
                )

        @ui.refreshable
        def global_stats_table():
            if not global_stats_data:
                ui.label("No seeded global rule data found yet. Click 'Reseed Global Data' to populate.").classes("text-sm text-gray-400 italic")
                return
            cols = [
                {"name": "source", "label": "Rule System", "field": "source", "align": "left", "sortable": True},
                {"name": "attributes", "label": "Attrs", "field": "attributes", "align": "center"},
                {"name": "skills", "label": "Skills", "field": "skills", "align": "center"},
                {"name": "classes", "label": "Classes", "field": "classes", "align": "center"},
                {"name": "weapons", "label": "Weapons", "field": "weapons", "align": "center"},
                {"name": "armor", "label": "Armor", "field": "armor", "align": "center"},
                {"name": "items", "label": "Gear", "field": "items", "align": "center"},
                {"name": "spells", "label": "Spells", "field": "spells", "align": "center"},
                {"name": "abilities", "label": "Amps/Abilities", "field": "abilities", "align": "center"},
                {"name": "total", "label": "Total", "field": "total", "align": "center", "sortable": True},
            ]
            ui.table(
                columns=cols,
                rows=global_stats_data,
                row_key="source",
            ).classes("w-full").props("dense flat bordered dark hide-bottom")

        global_stats_table()

    # Load data on page load
    await load_users()
    await load_global_stats()
