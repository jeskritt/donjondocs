"""
AI Helper Docstring
Purpose: NiceGUI panel for the "Allies & Stat Blocks" tab on the character sheet. Lists `CharacterAlly` rows for the current character with sort, expand-to-render-markdown, add/edit dialogs, and a delete-confirmation dialog. All writes go through `app.services.ally_service` so RBAC and persistence stay consistent with the rest of the app.
Interactions:
- `app.services.ally_service`: list/create/update/delete entry points.
- `app.schemas.ally.{Ally, AllyCreate, AllyUpdate}`: state representation and dialog payloads.
- `app.ui.pages.character_sheet`: registers this section's refresh handle in the page-level `refresh_fns` list and supplies the shared `state` dict.
- `state["allies"]`: in-memory list of `Ally` snapshots, populated by `_reload`.
- `state["allies_sort"]`, `state["allies_expanded"]`: survive `_save` re-renders the same way the existing Features/Equipment tabs do.
"""

"""Allies & Stat Blocks panel for the character sheet."""

from nicegui import ui

from app.schemas.ally import Ally, AllyCreate, AllyUpdate
from app.services.ally_service import (
    create_ally,
    delete_ally,
    list_allies,
    update_ally,
)
from app.services.session import service_session
from app.ui.theme import DIALOG_CARD_STYLE, notify_error, notify_success


# Quick-pick suggestions surfaced in the type select. The field is free
# text on the model — users may type anything; these are just hints.
ALLY_TYPE_SUGGESTIONS = ["Contact", "Companion", "Pet", "Wildshape", "User Defined"]


def _render_allies(state, char_id, user):
    """Render the Allies & Stat Blocks panel.

    Returns the refreshable handle so the parent page can wire it into
    `refresh_fns` (so a top-level `_save` triggers a re-render here too).
    """
    state.setdefault("allies", [])
    state.setdefault("allies_sort", "name")
    state.setdefault("allies_expanded", set())

    async def _reload():
        async with service_session() as session:
            rows = await list_allies(session, char_id, user)
        state["allies"] = [Ally.model_validate(r) for r in rows]
        _section.refresh()

    def _sorted_allies() -> list[Ally]:
        key = state["allies_sort"]
        return sorted(
            state["allies"],
            key=lambda a: (a.ally_type.lower() if key == "type" else a.name.lower()),
        )

    def _open_editor(existing: Ally | None = None):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg").style(DIALOG_CARD_STYLE):
            ui.label("Edit Ally" if existing else "Add Ally").classes("text-lg font-bold mb-2 text-white")

            name_in = ui.input("Name", value=(existing.name if existing else "")).props("dense").classes("w-full")
            type_in = ui.select(
                options=ALLY_TYPE_SUGGESTIONS,
                value=(existing.ally_type if existing else ALLY_TYPE_SUGGESTIONS[0]),
                with_input=True,
                new_value_mode="add-unique",
                label="Type",
            ).props("dense").classes("w-full")
            body_in = ui.textarea(
                "Body",
                value=(existing.body_md if existing else ""),
            ).props("dense outlined autogrow").classes("w-full")
            ui.label("Body field supports Markdown.").classes("text-xs text-gray-500 -mt-2")

            async def _save_click():
                name = (name_in.value or "").strip()
                type_value = (type_in.value or "").strip()
                if not name or not type_value:
                    notify_error("Name and type are required.")
                    return
                async with service_session() as session:
                    try:
                        if existing is None:
                            await create_ally(
                                session, char_id,
                                AllyCreate(
                                    name=name,
                                    ally_type=type_value,
                                    body_md=body_in.value or "",
                                ),
                                user,
                            )
                        else:
                            await update_ally(
                                session, existing.id,
                                AllyUpdate(
                                    name=name,
                                    ally_type=type_value,
                                    body_md=body_in.value or "",
                                ),
                                user,
                            )
                    except Exception as e:
                        notify_error(f"Save failed: {e}")
                        return
                notify_success("Saved")
                dialog.close()
                await _reload()

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color:#94A3B8;")
                ui.button("Save", on_click=_save_click).props("unelevated color=primary")
        dialog.open()

    def _confirm_delete(ally: Ally):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm").style(
            "background: #1E1E2E; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px;"
        ):
            ui.label("Delete Ally").classes("text-lg font-semibold mb-2").style("color: #EF4444;")
            ui.label(f"Permanently delete {ally.name!r}?").style("color: #E2E8F0;")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def _do_delete():
                    async with service_session() as session:
                        try:
                            await delete_ally(session, ally.id, user)
                        except Exception as e:
                            notify_error(f"Delete failed: {e}")
                            return
                    notify_success(f"Deleted {ally.name}")
                    dialog.close()
                    await _reload()

                ui.button("Delete", on_click=_do_delete, icon="delete_forever").props("unelevated").style(
                    "background: #EF4444 !important; border-radius: 8px;"
                )
        dialog.open()

    @ui.refreshable
    def _section():
        with ui.column().classes("w-full gap-3"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Allies & Stat Blocks").classes("text-xl font-bold text-white")
                with ui.row().classes("items-center gap-2"):
                    ui.label("Sort:").classes("text-xs text-gray-400")
                    sort_select = ui.select(
                        options={"name": "Name", "type": "Type"},
                        value=state["allies_sort"],
                    ).props("dense outlined").classes("w-32")
                    sort_select.on_value_change(
                        lambda e: (state.__setitem__("allies_sort", e.value), _section.refresh())
                    )
                    ui.button("Add Ally", icon="add", on_click=lambda: _open_editor(None)).props("unelevated color=primary")

            allies = _sorted_allies()
            if not allies:
                ui.label("No allies yet. Click 'Add Ally' to create one.").classes("text-gray-400 italic")
                return

            for ally in allies:
                _render_ally_row(ally)

    def _render_ally_row(ally: Ally):
        is_open = ally.id in state["allies_expanded"]

        def _toggle():
            if ally.id in state["allies_expanded"]:
                state["allies_expanded"].discard(ally.id)
            else:
                state["allies_expanded"].add(ally.id)
            _section.refresh()

        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center justify-between cursor-pointer").on("click", _toggle):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("expand_more" if is_open else "chevron_right").classes("text-gray-400")
                    ui.label(ally.name).classes("text-base font-bold text-white")
                with ui.row().classes("items-center gap-3"):
                    ui.badge(ally.ally_type, color="indigo")
                    # Stop click propagation so the action buttons don't toggle the row.
                    with ui.row().classes("gap-1").on("click.stop", lambda: None):
                        ui.button(
                            icon="edit",
                            on_click=lambda a=ally: _open_editor(a),
                        ).props("flat round dense").classes("text-gray-300")
                        ui.button(
                            icon="delete",
                            on_click=lambda a=ally: _confirm_delete(a),
                        ).props("flat round dense").classes("text-red-400")
            if is_open:
                ui.separator()
                if ally.body_md.strip():
                    ui.markdown(ally.body_md).classes("w-full px-2 py-1 text-gray-200")
                else:
                    ui.label("(empty)").classes("text-gray-500 italic px-2 py-1")

    _section()

    # Background-load the initial list so the panel populates without
    # blocking the rest of the page.
    async def _initial_load():
        await _reload()

    ui.timer(0, _initial_load, once=True)
    return _section
