"""
AI Helper Docstring
Purpose: NiceGUI page at `/creatures` — the Creature Catalog. Lists every creature visible to the current user (own + public), with click-to-expand PHB-style stat-block rendering, per-creature search/filter, import/export, copy, and a "parse stat block" action that runs `creature_parser.parse_stat_block` against the body and applies the extracted metadata.
Interactions:
- `app.services.creature_service`: CRUD + visibility.
- `app.services.creature_parser.parse_stat_block`: best-effort metadata extraction.
- `app.services.creature_io.export_filename_for`: download filename.
- `app.schemas.char_sheet_global.{CREATURE_TYPES, CREATURE_SIZES}`: canonical lists for the select inputs.
- `app/ui/components/sheet/stat_block_template.md`: seed body for new creatures.

Visibility rules at the UI layer:
- Owner sees Edit + Delete icons (alongside Copy + Export available to everyone visible).
- Non-owners viewing a public creature see only Copy + Export.
- Public/private chip shows status on creatures the current user *owns*; foreign public rows are unchipped to keep the grid quiet.
"""

"""Creature catalog page."""

import json
import logging
from pathlib import Path

from nicegui import app, ui

from app.schemas.char_sheet_global import CREATURE_SIZES, CREATURE_TYPES
from app.schemas.creature import CreatureCreate, CreatureUpdate
from app.services._errors import CreatureServiceError
from app.services.creature_io import (
    EXPORT_VERSION,
    MAX_IMPORT_BYTES,
    export_filename_for,
    migrate_creature_data,
)
from app.services.creature_parser import parse_stat_block
from app.services.creature_service import (
    copy_creature,
    create_creature,
    delete_creature,
    get_creature,
    list_creatures_visible_to,
    update_creature,
)
from app.services.session import service_session
from app.ui.auth import current_user_context
from app.ui.async_helpers import defer_load
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar
from app.ui.theme import DIALOG_CARD_STYLE, apply_global_styles, notify_error, notify_success

logger = logging.getLogger(__name__)


# Same templates used to seed the Ally body — the catalog and the in-character
# stat blocks share authoring conventions, so they share the seed files.
# "monster" is the default; "vehicle" seeds a mech/starship/airship stat block.
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "components" / "sheet"
_TEMPLATES = {
    "monster": "stat_block_template.md",
    "vehicle": "vehicle_stat_block_template.md",
}


def _read_template(kind: str = "monster") -> str:
    fname = _TEMPLATES.get(kind, _TEMPLATES["monster"])
    return (_TEMPLATE_DIR / fname).read_text(encoding="utf-8")


@ui.page("/creatures")
async def creatures_page():
    """Render the catalog grid for the current user."""
    user = current_user_context()

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("Creature Catalog — DonjonDocs")

    build_header()
    build_sidebar()

    # In-memory state mirrored from the DB on each `_reload`. Lookup by id
    # keeps the per-card handlers cheap and avoids capturing stale rows.
    state: dict = {
        "rows": [],            # list of dicts produced by _row_to_dict
        "owner_usernames": {}, # owner_id -> username for "Owned by" display
        "filter_q": "",
        "filter_type": None,
        "filter_size": None,
        "expanded": set(),     # ids of currently-expanded cards
    }

    def _row_to_dict(row) -> dict:
        return {
            "id": row.id,
            "owner_id": row.owner_id,
            "name": row.name,
            "body_md": row.body_md,
            "creature_type": row.creature_type,
            "size": row.size,
            "challenge_rating": row.challenge_rating,
            "habitat": row.habitat,
            "is_public": row.is_public,
            "columns": row.columns,
        }

    async def _reload():
        async with service_session() as session:
            rows = await list_creatures_visible_to(session, user)
            state["rows"] = [_row_to_dict(r) for r in rows]
            # Resolve owner usernames for the visible set in one query.
            from sqlalchemy import select
            from app.models.user import User
            owner_ids = {r.owner_id for r in rows}
            if owner_ids:
                u_rows = await session.execute(
                    select(User.id, User.username).where(User.id.in_(owner_ids))
                )
                state["owner_usernames"] = {uid: uname for uid, uname in u_rows.all()}
            else:
                state["owner_usernames"] = {}
        _card_list.refresh()

    def _visible_rows() -> list[dict]:
        rows = state["rows"]
        q = (state["filter_q"] or "").strip().lower()
        t = state["filter_type"]
        s = state["filter_size"]
        out = []
        for r in rows:
            if q and q not in r["name"].lower():
                continue
            if t:
                chips = {c.strip().lower() for c in r["creature_type"].split(",")}
                if t.lower() not in chips:
                    continue
            if s and r["size"].lower() != s.lower():
                continue
            out.append(r)
        return out

    def _open_editor(existing: dict | None):
        """Open the create/edit dialog. `existing` None → create, else patch."""
        is_new = existing is None
        seed_body = _read_template() if is_new else existing["body_md"]
        # Decompose the comma-joined type into a list for the multi-select.
        initial_types = (
            [t.strip() for t in (existing["creature_type"].split(",") if existing else []) if t.strip()]
            if not is_new else []
        )

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl").style(DIALOG_CARD_STYLE):
            ui.label("New Creature" if is_new else "Edit Creature").classes(
                "text-lg font-bold mb-2 text-white"
            )

            name_in = ui.input("Name*", value=(existing["name"] if existing else "")).props("dense").classes("w-full")

            with ui.row().classes("w-full gap-2"):
                size_in = ui.select(
                    options=list(CREATURE_SIZES),
                    value=(existing["size"] if existing and existing["size"] in CREATURE_SIZES else None),
                    label="Size",
                    with_input=True,
                ).props("dense").classes("flex-1")
                cr_in = ui.input(
                    "Challenge Rating",
                    value=(existing["challenge_rating"] if existing else ""),
                    placeholder="0, 1/8, 1/4, 1/2, 1, 2, …",
                ).props("dense").classes("flex-1")

            type_in = ui.select(
                options=list(CREATURE_TYPES),
                value=initial_types,
                label="Type",
                multiple=True,
                with_input=True,
            ).props("dense use-chips").classes("w-full")

            habitat_in = ui.input(
                "Habitat",
                value=(existing["habitat"] if existing else "Any"),
                placeholder="Any (or comma-separated list)",
            ).props("dense").classes("w-full")

            with ui.row().classes("w-full items-center gap-4"):
                public_in = ui.checkbox(
                    "Public — visible to all logged-in users",
                    value=(existing["is_public"] if existing else False),
                )
                ui.label("Columns:").classes("text-sm text-gray-400 ml-4")
                columns_in = ui.toggle(
                    options=[1, 2],
                    value=(existing["columns"] if existing else 1),
                ).props("dense unelevated").classes("ml-2")

            body_in = ui.textarea("Body (Markdown)", value=seed_body).props(
                "dense outlined autogrow input-style='font-family: monospace; font-size: 12px;'"
            ).classes("w-full")
            ui.label("Body field supports Markdown — homebrewery stat block recommended.").classes(
                "text-xs text-gray-500 -mt-2"
            )

            # New creatures can seed from a Monster or Vehicle/mech template. Only
            # swap the body while it's still an untouched seed (or empty) so we
            # never clobber what the user has typed.
            if is_new:
                _seed_bodies = {_read_template(kind).strip() for kind in _TEMPLATES}

                def _swap_template(e):
                    body = (body_in.value or "").strip()
                    if body and body not in _seed_bodies:
                        return
                    body_in.set_value(_read_template((e.value or "Monster").lower()))

                with ui.row().classes("w-full items-center gap-2 -mt-1"):
                    ui.label("Seed template:").classes("text-xs text-gray-500")
                    ui.select(
                        options=["Monster", "Vehicle"], value="Monster",
                        on_change=_swap_template,
                    ).props("dense options-dense").classes("w-40")

            async def _apply_parser():
                """Run the parser against the current textarea content and
                populate matched metadata fields. Does NOT save — user must
                still click Save to persist."""
                parsed = parse_stat_block(body_in.value or "")
                if not parsed:
                    notify_error("Couldn't extract any stat-block fields.")
                    return
                applied = []
                if "name" in parsed:
                    name_in.set_value(parsed["name"]); applied.append("name")
                if "size" in parsed:
                    size_in.set_value(parsed["size"]); applied.append("size")
                if "creature_type" in parsed:
                    types_list = [t.strip() for t in parsed["creature_type"].split(",") if t.strip()]
                    type_in.set_value(types_list); applied.append("type")
                if "challenge_rating" in parsed:
                    cr_in.set_value(parsed["challenge_rating"]); applied.append("CR")
                notify_success(f"Updated from stat block: {', '.join(applied)}")

            async def _save_click():
                name = (name_in.value or "").strip()
                if not name:
                    notify_error("Name is required.")
                    return
                # Multi-select returns a list — join into the canonical CSV.
                types_value = ", ".join(type_in.value or []) if type_in.value else ""
                async with service_session() as session:
                    try:
                        if is_new:
                            payload = CreatureCreate(
                                name=name,
                                body_md=body_in.value or "",
                                creature_type=types_value,
                                size=size_in.value or "",
                                challenge_rating=(cr_in.value or "").strip(),
                                habitat=(habitat_in.value or "Any").strip() or "Any",
                                is_public=bool(public_in.value),
                                columns=int(columns_in.value or 1),
                            )
                            await create_creature(session, user, payload)
                        else:
                            patch = CreatureUpdate(
                                name=name,
                                body_md=body_in.value or "",
                                creature_type=types_value,
                                size=size_in.value or "",
                                challenge_rating=(cr_in.value or "").strip(),
                                habitat=(habitat_in.value or "Any").strip() or "Any",
                                is_public=bool(public_in.value),
                                columns=int(columns_in.value or 1),
                            )
                            await update_creature(session, existing["id"], patch, user)
                    except CreatureServiceError as exc:
                        notify_error(exc.message)
                        return
                    except Exception as exc:
                        logger.exception("creature save failed")
                        notify_error(f"Save failed: {exc}")
                        return
                notify_success("Saved")
                dialog.close()
                await _reload()

            with ui.row().classes("w-full justify-between mt-3 gap-2"):
                ui.button(
                    "Update from stat block",
                    icon="auto_fix_high",
                    on_click=_apply_parser,
                ).props("flat").style("color: #818CF8;")
                with ui.row().classes("gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")
                    ui.button("Save", on_click=_save_click).props("unelevated color=primary")
        dialog.open()

    def _confirm_delete(creature: dict):
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm").style(
            "background: #1E1E2E; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px;"
        ):
            ui.label("Delete Creature").classes("text-lg font-semibold mb-2").style("color: #EF4444;")
            ui.label(f"Permanently delete {creature['name']!r}?").style("color: #E2E8F0;")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").style("color: #94A3B8;")

                async def _do_delete():
                    async with service_session() as session:
                        try:
                            await delete_creature(session, creature["id"], user)
                        except CreatureServiceError as exc:
                            notify_error(exc.message)
                            return
                    notify_success(f"Deleted {creature['name']}")
                    dialog.close()
                    await _reload()

                ui.button("Delete", on_click=_do_delete, icon="delete_forever").props("unelevated").style(
                    "background: #EF4444 !important; border-radius: 8px;"
                )
        dialog.open()

    async def _do_copy(creature: dict):
        async with service_session() as session:
            try:
                new_row = await copy_creature(session, creature["id"], user)
            except CreatureServiceError as exc:
                notify_error(exc.message)
                return
        notify_success(f"Copied as {new_row.name!r}")
        await _reload()
        # Open the editor on the new row so the user can rename / tweak.
        new_dict = next((r for r in state["rows"] if r["id"] == new_row.id), None)
        if new_dict:
            _open_editor(new_dict)

    async def _do_export(creature: dict):
        async with service_session() as session:
            try:
                row = await get_creature(session, creature["id"], user)
            except CreatureServiceError as exc:
                notify_error(exc.message)
                return
        envelope = {
            "version": EXPORT_VERSION,
            "exported_at": row.updated_at.isoformat() if row.updated_at else None,
            "creature_data": {
                "name": row.name,
                "body_md": row.body_md,
                "creature_type": row.creature_type,
                "size": row.size,
                "challenge_rating": row.challenge_rating,
                "habitat": row.habitat,
                "is_public": False,
                "columns": row.columns,
            },
        }
        content = json.dumps(envelope, indent=2, default=str).encode()
        ui.download(content, filename=f"{export_filename_for(row.name)}.json")

    def _open_import_dialog():
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md").style(DIALOG_CARD_STYLE):
            ui.label("Import Creature").classes("text-lg font-bold mb-2 text-white")
            ui.label("Upload a .json file exported from the Creature Catalog.").classes(
                "text-sm text-gray-400 mb-4"
            )

            async def _handle_upload(e):
                if e.file.size() > MAX_IMPORT_BYTES:
                    notify_error(f"Import file exceeds {MAX_IMPORT_BYTES} bytes.")
                    return
                try:
                    envelope = await e.file.json()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    notify_error("Invalid JSON file.")
                    return
                if not isinstance(envelope, dict) or "creature_data" not in envelope:
                    notify_error("Missing 'creature_data' in import file.")
                    return
                version = envelope.get("version", EXPORT_VERSION)
                if not isinstance(version, int):
                    notify_error("Envelope 'version' must be an integer.")
                    return
                try:
                    data = migrate_creature_data(dict(envelope["creature_data"]), version)
                except CreatureServiceError as exc:
                    notify_error(exc.message)
                    return
                except Exception:
                    notify_error("Creature data failed migration.")
                    return
                data["is_public"] = False
                try:
                    payload = CreatureCreate.model_validate(data)
                except Exception:
                    notify_error("Creature data failed validation.")
                    return
                async with service_session() as session:
                    try:
                        rec = await create_creature(session, user, payload)
                    except CreatureServiceError as exc:
                        notify_error(exc.message)
                        return
                notify_success(f"Imported {rec.name!r}")
                dialog.close()
                await _reload()

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

    def _build_header_and_filters():
        """Render the page header + the filter row.

        Kept outside `_card_list`'s refreshable so the search input is not
        torn down on every keystroke — that rebuild is what made the
        catalog feel like it only accepted one character at a time. The
        700-line cure was worse than the disease here: a 300 ms Quasar
        debounce on the input + a smaller refreshable scope below is all
        we need.
        """
        with ui.row().classes("w-full items-center justify-between mb-4 gap-3 flex-wrap"):
            ui.label("Creature Catalog").classes("text-2xl font-bold text-white")
            with ui.row().classes("gap-2 items-center"):
                ui.button("Import", icon="upload", on_click=_open_import_dialog).props(
                    "unelevated"
                ).style("background: #374151 !important; border-radius: 8px;")
                ui.button(
                    "New Creature",
                    icon="add",
                    on_click=lambda: _open_editor(None),
                ).props("unelevated").style(
                    "background: #4F46E5 !important; border-radius: 8px;"
                )

        with ui.row().classes("w-full items-center gap-2 mb-4 flex-wrap"):
            search_in = ui.input(
                placeholder="Search name…",
                value=state["filter_q"],
            ).props("dense outlined clearable debounce=300").classes("flex-1 min-w-[200px]")
            search_in.on_value_change(
                lambda e: (state.__setitem__("filter_q", e.value or ""), _card_list.refresh())
            )
            type_filter = ui.select(
                options=list(CREATURE_TYPES),
                value=state["filter_type"],
                label="Type",
                clearable=True,
                with_input=True,
            ).props("dense").classes("min-w-[180px]")
            type_filter.on_value_change(
                lambda e: (state.__setitem__("filter_type", e.value), _card_list.refresh())
            )
            size_filter = ui.select(
                options=list(CREATURE_SIZES),
                value=state["filter_size"],
                label="Size",
                clearable=True,
            ).props("dense").classes("min-w-[140px]")
            size_filter.on_value_change(
                lambda e: (state.__setitem__("filter_size", e.value), _card_list.refresh())
            )

    @ui.refreshable
    def _card_list():
        """Refreshable scope is now just the empty-state + card grid.

        The filter inputs above are stable across `_card_list.refresh()`
        calls so focus / typed-in-progress text survives a refilter.
        """
        rows = _visible_rows()
        if not rows:
            ui.label(
                "No creatures yet. Click 'New Creature' to author one, or "
                "'Import' to load an exported .json."
            ).classes("text-gray-400 italic mt-4")
            return

        with ui.column().classes("w-full gap-3"):
            for row in rows:
                _render_card(row)

    def _render_card(creature: dict):
        is_owner = creature["owner_id"] == user.id
        is_open = creature["id"] in state["expanded"]
        owner_username = state["owner_usernames"].get(creature["owner_id"], "")
        owner_label = "me" if is_owner else (owner_username or "another player")

        def _toggle():
            if creature["id"] in state["expanded"]:
                state["expanded"].discard(creature["id"])
            else:
                state["expanded"].add(creature["id"])
            _card_list.refresh()

        with ui.card().classes("w-full"):
            # Header row: name + badges on the left, action icons on the right.
            with ui.row().classes("w-full items-center justify-between cursor-pointer").on(
                "click", _toggle
            ):
                with ui.row().classes("items-center gap-3 flex-wrap"):
                    ui.icon("expand_more" if is_open else "chevron_right").classes("text-gray-400")
                    ui.label(creature["name"]).classes("text-base font-bold text-white")
                    if creature["size"]:
                        ui.badge(creature["size"], color="grey")
                    if creature["creature_type"]:
                        ui.badge(creature["creature_type"], color="indigo")
                    if creature["challenge_rating"]:
                        ui.badge(f"CR {creature['challenge_rating']}", color="amber").props("text-color=black")
                    # Owned-by chip — quietly indicates non-self ownership.
                    ui.label(f"Owned by: {owner_label}").classes("text-xs text-gray-500 ml-2")
                    # Public/private indicator (only on owned rows to keep the
                    # grid visually quiet for foreign public creatures).
                    if is_owner:
                        if creature["is_public"]:
                            ui.badge("Public", color="indigo").props("outline")
                        else:
                            ui.badge("Private", color="grey").props("outline")

                with ui.row().classes("gap-1").on("click.stop", lambda: None):
                    if is_owner:
                        ui.button(
                            icon="edit",
                            on_click=lambda c=creature: _open_editor(c),
                        ).props("flat round dense").classes("text-gray-300").tooltip("Edit")
                    ui.button(
                        icon="content_copy",
                        on_click=lambda c=creature: _do_copy(c),
                    ).props("flat round dense").classes("text-gray-300").tooltip("Copy")
                    ui.button(
                        icon="download",
                        on_click=lambda c=creature: _do_export(c),
                    ).props("flat round dense").classes("text-gray-300").tooltip("Export")
                    if is_owner:
                        ui.button(
                            icon="delete",
                            on_click=lambda c=creature: _confirm_delete(c),
                        ).props("flat round dense").classes("text-red-400").tooltip("Delete")

            if is_open:
                ui.separator()
                if (creature["body_md"] or "").strip():
                    classes = "phb phb-cols-2" if creature["columns"] == 2 else "phb"
                    ui.markdown(creature["body_md"]).classes(f"w-full px-2 py-1 {classes}")
                else:
                    ui.label("(empty)").classes("text-gray-500 italic px-2 py-1")

    with ui.column().classes("page-content"):
        _build_header_and_filters()
        _card_list()

    # Initial load happens after the UI is mounted so the page paints fast.
    async def _initial_load():
        await _reload()

    defer_load(_initial_load)
