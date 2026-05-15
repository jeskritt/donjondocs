"""
AI Helper Docstring
Purpose: NiceGUI panel for the "Notes" tab on the character sheet. Lists `CharacterNote` rows for the current character with sort, expand-to-render-markdown, add/edit dialogs, and a delete-confirmation dialog. All writes go through `app.services.note_service`.
Interactions:
- `app.services.note_service`: list/create/update/delete entry points.
- `app.schemas.note.{Note, NoteCreate, NoteUpdate}`: state representation and dialog payloads.
- `app.ui.pages.character_sheet`: registers this section's refresh handle in `refresh_fns` and supplies the shared `state` dict.
- `state["notes"]`: in-memory list of `Note` snapshots, populated by `_reload`.
- `state["notes_sort"]`, `state["notes_expanded"]`: survive `_save` re-renders.
"""

"""Notes panel for the character sheet."""

from nicegui import app, ui

from app.schemas.note import Note, NoteCreate, NoteUpdate
from app.services.note_service import (
    create_note,
    delete_note,
    list_notes,
    update_note,
)
from app.services.session import service_session
from app.ui.async_helpers import defer_load
from app.ui.theme import DIALOG_CARD_STYLE, notify_error, notify_success


def _render_notes(state, char_id, user):
    """Render the Notes panel.

    Returns the refreshable handle so the parent page can wire it into
    `refresh_fns`.
    """
    state.setdefault("notes", [])
    # "created" sorts newest-first; "title" sorts alphabetically ascending.
    state.setdefault("notes_sort", "created")
    state.setdefault("notes_expanded", set())

    async def _reload():
        async with service_session() as session:
            rows = await list_notes(session, char_id, user)
        state["notes"] = [Note.model_validate(r) for r in rows]
        _section.refresh()

    def _sorted_notes() -> list[Note]:
        if state["notes_sort"] == "title":
            return sorted(state["notes"], key=lambda n: n.title.lower())
        # Default: newest first by creation date.
        return sorted(state["notes"], key=lambda n: n.created_at, reverse=True)

    def _open_editor(existing: Note | None = None):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg").style(DIALOG_CARD_STYLE):
            ui.label("Edit Note" if existing else "Add Note").classes("text-lg font-bold mb-2 text-white")

            title_in = ui.input("Title", value=(existing.title if existing else "")).props("dense").classes("w-full")
            body_in = ui.textarea(
                "Body",
                value=(existing.body_md if existing else ""),
            ).props("dense outlined autogrow").classes("w-full")
            ui.label("Body field supports Markdown.").classes("text-xs text-gray-500 -mt-2")

            async def _save_click():
                title = (title_in.value or "").strip()
                if not title:
                    notify_error("Title is required.")
                    return
                async with service_session() as session:
                    try:
                        if existing is None:
                            await create_note(
                                session, char_id,
                                NoteCreate(title=title, body_md=body_in.value or ""),
                                user,
                            )
                        else:
                            await update_note(
                                session, existing.id,
                                NoteUpdate(title=title, body_md=body_in.value or ""),
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

    def _confirm_delete(note: Note):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm").style(
            "background: #1E1E2E; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px;"
        ):
            ui.label("Delete Note").classes("text-lg font-semibold mb-2").style("color: #EF4444;")
            ui.label(f"Permanently delete {note.title!r}?").style("color: #E2E8F0;")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def _do_delete():
                    async with service_session() as session:
                        try:
                            await delete_note(session, note.id, user)
                        except Exception as e:
                            notify_error(f"Delete failed: {e}")
                            return
                    notify_success(f"Deleted {note.title}")
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
                ui.label("Notes").classes("text-xl font-bold text-white")
                with ui.row().classes("items-center gap-2"):
                    ui.label("Sort:").classes("text-xs text-gray-400")
                    sort_select = ui.select(
                        options={"created": "Newest", "title": "Title"},
                        value=state["notes_sort"],
                    ).props("dense outlined").classes("w-32")
                    sort_select.on_value_change(
                        lambda e: (state.__setitem__("notes_sort", e.value), _section.refresh())
                    )
                    ui.button("Add Note", icon="add", on_click=lambda: _open_editor(None)).props("unelevated color=primary")

            notes = _sorted_notes()
            if not notes:
                ui.label("No notes yet. Click 'Add Note' to create one.").classes("text-gray-400 italic")
                return

            for note in notes:
                _render_note_row(note)

    def _render_note_row(note: Note):
        is_open = note.id in state["notes_expanded"]

        def _toggle():
            if note.id in state["notes_expanded"]:
                state["notes_expanded"].discard(note.id)
            else:
                state["notes_expanded"].add(note.id)
            _section.refresh()

        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center justify-between cursor-pointer").on("click", _toggle):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("expand_more" if is_open else "chevron_right").classes("text-gray-400")
                    ui.label(note.title).classes("text-base font-bold text-white")
                with ui.row().classes("items-center gap-3"):
                    ui.label(note.created_at.strftime("%Y-%m-%d")).classes("text-xs text-gray-400")
                    with ui.row().classes("gap-1").on("click.stop", lambda: None):
                        ui.button(
                            icon="edit",
                            on_click=lambda n=note: _open_editor(n),
                        ).props("flat round dense").classes("text-gray-300")
                        ui.button(
                            icon="delete",
                            on_click=lambda n=note: _confirm_delete(n),
                        ).props("flat round dense").classes("text-red-400")
            if is_open:
                ui.separator()
                if note.body_md.strip():
                    # When PHB is on, drop text-gray-200 so the vendored
                    # parchment-friendly colors win cleanly. Off → keep the
                    # Tailwind utility for legible dark-mode text.
                    color_class = "phb" if app.storage.user.get("phb_style") else "text-gray-200"
                    ui.markdown(note.body_md).classes(f"w-full px-2 py-1 {color_class}")
                else:
                    ui.label("(empty)").classes("text-gray-500 italic px-2 py-1")

    _section()

    async def _initial_load():
        await _reload()

    defer_load(_initial_load)
    return _section
