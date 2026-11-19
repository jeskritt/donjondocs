"""Character management page — /characters

Lists user's characters with actions: open, export (JSON download), delete.
Import button opens an upload dialog to create a character from an exported JSON file.
"""

import json
import logging

from nicegui import ui

logger = logging.getLogger(__name__)

from app.schemas.char_sheet_global import SheetStyle
from app.services.character_io import EXPORT_VERSION, MAX_IMPORT_BYTES, export_filename_for
from app.services.character_service import (
    CharacterServiceError,
    delete_character,
    export_character,
    import_character,
    list_user_characters,
)
from app.services.session import service_session
from app.ui.auth import current_user_context
from app.ui.theme import DIALOG_CARD_STYLE, apply_global_styles, notify_error, notify_success
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar


@ui.page("/characters")
async def characters_page():
    """List characters for the current user."""
    user = current_user_context()

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("My Characters — DonjonDocs")

    build_header()
    build_sidebar()

    characters_data = []

    async def load_characters():
        nonlocal characters_data
        async with service_session() as session:
            chars = await list_user_characters(session, user.id)
            characters_data = [
                {
                    "id": c.id,
                    "name": c.name,
                    "style": c.style.value,
                    "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else "-",
                }
                for c in chars
            ]
        chars_table.refresh()

    def show_delete_dialog(char_row: dict):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm").style(
            "background: #1E1E2E; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px;"
        ):
            ui.label("Delete Character").classes("text-lg font-semibold mb-2").style("color: #EF4444;")
            ui.label(f"Are you sure you want to permanently delete {char_row['name']}?").style("color: #E2E8F0;")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def do_delete():
                    async with service_session() as session:
                        try:
                            await delete_character(session, char_row["id"], user)
                            notify_success(f"Deleted {char_row['name']}")
                            dialog.close()
                            await load_characters()
                        except CharacterServiceError as e:
                            notify_error(e.message)
                        except Exception as e:
                            notify_error(f"Error deleting character: {e}")

                ui.button("Delete", on_click=do_delete, icon="delete_forever").props("unelevated").style(
                    "background: #EF4444 !important; border-radius: 8px;"
                )
        dialog.open()

    async def handle_export(e):
        char_row = e.args
        try:
            async with service_session() as session:
                data = await export_character(session, char_row["id"], user)
            content = json.dumps(data, indent=2, default=str).encode()
            safe_name = export_filename_for(data["name"])
            ui.download(content, filename=f"{safe_name}.json")
        except CharacterServiceError as exc:
            notify_error(exc.message)
        except Exception as exc:
            notify_error(f"Export failed: {exc}")

    def _open_import_dialog():
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md").style(
            DIALOG_CARD_STYLE
        ):
            ui.label("Import Character").classes("text-lg font-bold mb-2 text-white")
            ui.label("Upload a .json file exported from DonjonDocs.").classes("text-sm text-gray-400 mb-4")

            async def _handle_upload(e):
                if e.file.size() > MAX_IMPORT_BYTES:
                    notify_error(f"Import file exceeds {MAX_IMPORT_BYTES} bytes.")
                    return
                try:
                    envelope = await e.file.json()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    notify_error("Invalid JSON file.")
                    return

                if not isinstance(envelope, dict) or "character_data" not in envelope:
                    notify_error("Missing 'character_data' in import file.")
                    return

                name = envelope.get("name", "Imported Character")
                style_str = envelope.get("style", "dnd5e")
                try:
                    style = SheetStyle(style_str)
                except ValueError:
                    notify_error(f"Unknown game system: {style_str}")
                    return

                version = envelope.get("version", EXPORT_VERSION)
                if not isinstance(version, int):
                    notify_error("Envelope 'version' must be an integer.")
                    return

                try:
                    async with service_session() as session:
                        rec = await import_character(
                            session, name, style, envelope["character_data"], user,
                            version=version,
                            allies=envelope.get("allies"),
                            notes=envelope.get("notes"),
                        )
                    notify_success(f"Imported '{rec.name}' successfully!")
                    dialog.close()
                    await load_characters()
                except CharacterServiceError as exc:
                    notify_error(exc.message)
                except Exception:
                    logger.exception("character import failed")
                    notify_error("Character data failed validation. Is this a valid export?")

            # `add-icon` swaps the q-uploader "+" picker button for an upload
            # arrow so the affordance reads as "upload a file" rather than
            # "add a row". `upload-icon` is set for parity if auto-upload
            # ever gets toggled off and the manual upload button shows up.
            ui.upload(
                on_upload=_handle_upload,
                on_rejected=lambda _: notify_error(
                    f"Upload rejected (only .json files up to {MAX_IMPORT_BYTES // (1024 * 1024)} MiB are accepted)."
                ),
                auto_upload=True,
                max_files=1,
                max_file_size=MAX_IMPORT_BYTES,
            ).props('accept=".json"').classes("w-full")

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")
        dialog.open()


    with ui.column().classes("page-content"):
        with ui.row().classes("w-full items-center justify-between mb-6"):
            ui.label("My Characters").classes("text-2xl font-bold text-white")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Import",
                    on_click=_open_import_dialog,
                    icon="upload",
                ).props("unelevated").style(
                    "background: #374151 !important; border-radius: 8px;"
                )
                ui.button(
                    "New Sheet",
                    on_click=lambda: ui.navigate.to("/sheet/new"),
                    icon="add",
                ).props("unelevated").style(
                    "background: #4F46E5 !important; border-radius: 8px;"
                )

        @ui.refreshable
        def chars_table():
            if not characters_data:
                ui.label("No characters found. Create one to get started!").classes("text-gray-400 mt-4")
                return

            columns = [
                {"name": "name", "label": "Character Name", "field": "name", "align": "left", "sortable": True},
                {"name": "style", "label": "Game System", "field": "style", "align": "left", "sortable": True},
                {"name": "updated_at", "label": "Last Updated", "field": "updated_at", "align": "center", "sortable": True},
                {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
            ]

            table = ui.table(
                columns=columns,
                rows=characters_data,
                row_key="id",
                pagination={"rowsPerPage": 25},
            ).classes("w-full mt-4").props("flat bordered dark")

            table.add_slot("body-cell-style", '''
                <q-td :props="props">
                    <q-badge color="indigo" :label="props.row.style" />
                </q-td>
            ''')

            # The action cell stops row-click propagation so per-row buttons
            # don't double-fire the "open" handler below.
            table.add_slot("body-cell-actions", r'''
                <q-td :props="props" @click.stop>
                    <q-btn flat round dense icon="login" title="Open Sheet" @click.stop="$parent.$emit('open', props.row)" size="sm" color="primary" />
                    <q-btn flat round dense icon="download" title="Export" @click.stop="$parent.$emit('export', props.row)" size="sm" color="teal" />
                    <q-btn flat round dense icon="delete" title="Delete" @click.stop="$parent.$emit('delete', props.row)" size="sm" color="negative" />
                </q-td>
            ''')

            def handle_open(e):
                ui.navigate.to(f"/character/{e.args['id']}")

            def handle_delete(e):
                show_delete_dialog(e.args)

            table.on("open", handle_open)
            table.on("export", handle_export)
            table.on("delete", handle_delete)
            # Click anywhere on a row (outside the action buttons) opens the sheet.
            # Quasar's row-click event payload is (evt, row, idx); we only need row.
            table.on("row-click", lambda e: ui.navigate.to(f"/character/{e.args[1]['id']}"))

        chars_table()

    await load_characters()
