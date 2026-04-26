from nicegui import ui

from app.ui.components.sheet.helpers import make_toggle_handler


def _render_proficiencies(state, char_id, user, _save):
    @ui.refreshable
    def _section():
        cs = state["cs"]
        prof = cs.proficiency
        is_editing = [False]

        with ui.card().classes('w-full flex-1 min-w-[260px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Proficiencies").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            categories = [
                ("Weapons", prof.weapon), ("Armor", prof.armor), ("Languages", prof.language),
                ("Tools", prof.tool), ("Instruments", prof.instrument), ("Games", prof.game),
            ]
            display_col = ui.column().classes('w-full')
            edit_col = ui.column().classes('w-full')
            inputs = {}

            with display_col:
                for cat, items in categories:
                    with ui.row().classes('w-full border-b border-gray-800 py-1 items-start'):
                        ui.label(f"{cat}:").classes('text-gray-400 w-24 shrink-0')
                        ui.label(', '.join(items) if items else '—').classes('text-white text-sm flex-1')

            with edit_col:
                for cat, items in categories:
                    inputs[cat.lower()] = ui.input(cat, value=', '.join(items)).classes('w-full').props('dense')

                async def _save_prof():
                    await _save({"proficiency": {
                        "weapon":     [v.strip() for v in (inputs["weapons"].value or "").split(",") if v.strip()],
                        "armor":      [v.strip() for v in (inputs["armor"].value or "").split(",") if v.strip()],
                        "language":   [v.strip() for v in (inputs["languages"].value or "").split(",") if v.strip()],
                        "tool":       [v.strip() for v in (inputs["tools"].value or "").split(",") if v.strip()],
                        "instrument": [v.strip() for v in (inputs["instruments"].value or "").split(",") if v.strip()],
                        "game":       [v.strip() for v in (inputs["games"].value or "").split(",") if v.strip()],
                    }})

                ui.button("Save", on_click=_save_prof).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

    _section()
    return _section
