from nicegui import ui

from app.ui.components.sheet.helpers import make_toggle_handler


def _render_hp(state, char_id, user, _save):
    @ui.refreshable
    def _section():
        cs = state["cs"]
        combat = state["vd"].get("combat", {})
        exhaustion_label = combat.get("exhaustion_label", "Exhaustion")
        show_strife = combat.get("show_strife", False)
        is_editing = [False]

        with ui.card().classes('w-full flex-1 min-w-[260px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Hit Points").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            display_col = ui.column().classes('w-full')
            edit_col = ui.column().classes('w-full')

            with display_col:
                rows = [
                    ("Current / Max", f"{cs.hp_current} / {cs.hp_max}"),
                    ("Temporary", str(cs.hp_temp)),
                    (exhaustion_label, f"{cs.exhaustion} / 6"),
                ]
                if show_strife:
                    rows.append(("Strife", f"{cs.strife} / 6"))
                for label, val in rows:
                    with ui.row().classes('w-full justify-between border-b border-gray-800 py-1'):
                        ui.label(label).classes('text-gray-400')
                        ui.label(val).classes('text-white font-bold' if label == "Current / Max" else 'text-white')
                for hd in combat.get("hit_dice", []):
                    with ui.row().classes('w-full justify-between border-b border-gray-800 py-1'):
                        ui.label(f"HD ({hd['class_name']} {hd['die']})").classes('text-gray-400')
                        ui.label(f"{hd['current']} / {hd['maximum']}").classes('text-white')
                for def_label, def_val in [
                    ("Resistances", combat.get("resistances", "")),
                    ("Immunities", combat.get("immunities", "")),
                    ("Vulnerabilities", combat.get("vulnerabilities", "")),
                ]:
                    if def_val:
                        with ui.row().classes('w-full justify-between border-b border-gray-800 py-1'):
                            ui.label(def_label).classes('text-gray-400')
                            ui.label(def_val).classes('text-white text-sm')

            with edit_col:
                hp_cur  = ui.number("Current HP", value=cs.hp_current, step=1).classes('w-full').props('dense')
                hp_max  = ui.number("Max HP", value=cs.hp_max, step=1, min=1).classes('w-full').props('dense')
                hp_temp = ui.number("Temp HP", value=cs.hp_temp, step=1, min=0).classes('w-full').props('dense')
                exh_inp = ui.number(exhaustion_label, value=cs.exhaustion, step=1, min=0, max=6).classes('w-full').props('dense')
                strife_inp = (
                    ui.number("Strife", value=cs.strife, step=1, min=0, max=6).classes('w-full').props('dense')
                    if show_strife else None
                )
                res_inp  = ui.input("Resistances", value=cs.resistances).classes('w-full').props('dense')
                imm_inp  = ui.input("Immunities", value=cs.immunities).classes('w-full').props('dense')
                vul_inp  = ui.input("Vulnerabilities", value=cs.vulnerabilities).classes('w-full').props('dense')

                async def _save_hp():
                    updates = {
                        "hp_current": int(hp_cur.value or 0),
                        "hp_max":     int(hp_max.value or 1),
                        "hp_temp":    int(hp_temp.value or 0),
                        "exhaustion": int(exh_inp.value or 0),
                        "resistances": (res_inp.value or "").strip(),
                        "immunities": (imm_inp.value or "").strip(),
                        "vulnerabilities": (vul_inp.value or "").strip(),
                    }
                    if strife_inp is not None:
                        updates["strife"] = int(strife_inp.value or 0)
                    await _save(updates)

                ui.button("Save", on_click=_save_hp).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

    _section()
    return _section
