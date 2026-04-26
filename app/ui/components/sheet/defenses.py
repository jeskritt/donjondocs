from nicegui import ui

from app.ui.components.sheet.helpers import make_toggle_handler


def _render_defenses(state, char_id, user, _save):
    @ui.refreshable
    def _section():
        top = state["vd"].get("top_bar", {})
        cs = state["cs"]
        is_editing = [False]

        with ui.card().classes('w-full flex-1 min-w-[260px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Defenses").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            display_col = ui.column().classes('w-full')
            edit_col = ui.column().classes('w-full')

            ac_bd = state["vd"].get('ac_breakdown', {})

            with display_col:
                ac_subline = (
                    f"{ac_bd.get('base', 0)} base"
                    f" + {ac_bd.get('dex', 0)} DEX"
                    + (f" + {ac_bd.get('shield', 0)} shield" if ac_bd.get('shield') else "")
                    + (f" + {ac_bd.get('misc', 0)} misc" if ac_bd.get('misc') else "")
                ) if ac_bd else None

                rows = [
                    ("AC", str(top.get('ac', 10))),
                    ("Initiative", str(top.get('initiative', '+0'))),
                    ("Speed", str(cs.speed)),
                    ("Conditions", ', '.join(top.get('conditions', [])) or 'None'),
                ]
                if top.get('inspiration') is not None:
                    rows.append(("Inspiration", "Yes" if top.get('inspiration') else "No"))
                for label, val in rows:
                    with ui.row().classes('w-full justify-between border-b border-gray-800 py-1'):
                        ui.label(label).classes('text-gray-400')
                        ui.label(val).classes('text-white')
                if ac_subline:
                    ui.label(ac_subline).classes('text-gray-500 text-xs italic')

            with edit_col:
                armor_locked = bool(ac_bd.get('armor_locked'))
                ac_base = ui.number("AC Base", value=cs.ac.base, step=1, min=0).classes('w-full').props('dense')
                if armor_locked:
                    ac_base.props('readonly')
                    ui.label(f"Base locked by equipped armor: {ac_bd.get('armor_name')}").classes('text-gray-500 text-xs italic')
                ac_misc = ui.number("AC Misc", value=cs.ac.misc, step=1).classes('w-full').props('dense')
                init_base = ui.number("Initiative Base", value=cs.initiative.base, step=1).classes('w-full').props('dense')
                init_misc = ui.number("Initiative Misc", value=cs.initiative.misc, step=1).classes('w-full').props('dense')
                speed_inp = ui.number("Speed", value=cs.speed, step=5, min=0).classes('w-full').props('dense')
                cond_inp  = ui.input("Conditions (comma-separated)", value=', '.join(cs.conditions)).classes('w-full').props('dense')
                insp_toggle = None
                if cs.inspiration is not None:
                    insp_toggle = ui.checkbox("Inspiration", value=bool(cs.inspiration))

                async def _save_defenses():
                    updates = {
                        "ac":         {"base": int(ac_base.value or 10), "misc": int(ac_misc.value or 0)},
                        "initiative": {"base": int(init_base.value or 0), "misc": int(init_misc.value or 0)},
                        "speed":      int(speed_inp.value or 0),
                        "conditions": [c.strip() for c in cond_inp.value.split(",") if c.strip()],
                    }
                    if insp_toggle is not None:
                        updates["inspiration"] = insp_toggle.value
                    await _save(updates)

                ui.button("Save", on_click=_save_defenses).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

    _section()
    return _section
