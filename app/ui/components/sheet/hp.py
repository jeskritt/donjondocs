from nicegui import ui

from app.ui.components.sheet.helpers import make_toggle_handler, render_pm_adjuster


def _render_hp(state, char_id, user, _save):
    @ui.refreshable
    def _section():
        cs = state["cs"]
        combat = state["vd"].get("combat", {})
        exhaustion_label = combat.get("exhaustion_label", "Exhaustion")
        exhaustion_tooltip = combat.get("exhaustion_tooltip")
        show_strife = combat.get("show_strife", False)
        show_death_saves = combat.get("show_death_saves", False)
        is_editing = [False]

        with ui.card().classes('w-full flex-1 min-w-[260px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Hit Points").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            display_col = ui.column().classes('w-full')
            edit_col = ui.column().classes('w-full')

            with display_col:
                async def _hp_adjust(delta: int):
                    new_val = max(0, min(cs.hp_max, cs.hp_current + delta))
                    await _save({"hp_current": new_val})

                async def _temp_adjust(delta: int):
                    new_val = max(0, cs.hp_temp + delta)
                    await _save({"hp_temp": new_val})

                async def _exh_adjust(delta: int):
                    new_val = max(0, min(6, cs.exhaustion + delta))
                    await _save({"exhaustion": new_val})

                async def _strife_adjust(delta: int):
                    new_val = max(0, min(6, cs.strife + delta))
                    await _save({"strife": new_val})

                adjustable_rows = [
                    ("Current / Max", f"{cs.hp_current} / {cs.hp_max}", _hp_adjust, True),
                    ("Temporary", str(cs.hp_temp), _temp_adjust, False),
                    (exhaustion_label, f"{cs.exhaustion} / 6", _exh_adjust, False),
                ]
                if show_strife:
                    adjustable_rows.append(("Strife", f"{cs.strife} / 6", _strife_adjust, False))

                for label, val, on_delta, is_hp in adjustable_rows:
                    with ui.row().classes('w-full justify-between items-center border-b border-gray-800 py-1'):
                        lbl = ui.label(label).classes('text-gray-400')
                        if label == exhaustion_label and exhaustion_tooltip:
                            lbl.tooltip(exhaustion_tooltip)
                        with ui.row().classes('items-center gap-1'):
                            render_pm_adjuster(on_delta)
                            ui.label(val).classes('text-white font-bold ml-2' if is_hp else 'text-white ml-2')

                    if is_hp and cs.hp_max > 0:
                        async def _hp_set(value):
                            new_val = max(0, min(cs.hp_max, int(value or 0)))
                            if new_val != cs.hp_current:
                                await _save({"hp_current": new_val})
                        hp_slider = ui.slider(min=0, max=cs.hp_max, step=1, value=cs.hp_current) \
                            .props('dense color=red label') \
                            .classes('w-full')
                        hp_slider.on('change', lambda e: _hp_set(e.args))

                for hd in combat.get("hit_dice", []):
                    cls_name = hd['class_name']

                    def _make_hd_adjust(name):
                        async def _hd_adjust(delta: int):
                            updated = []
                            for ce in cs.classes:
                                d = ce.model_dump()
                                if ce.name == name:
                                    cur = ce.hit_dice_current if ce.hit_dice_current is not None else 0
                                    mx = ce.hit_dice_max if ce.hit_dice_max is not None else 0
                                    d["hit_dice_current"] = max(0, min(mx, cur + delta))
                                updated.append(d)
                            await _save({"classes": updated})
                        return _hd_adjust

                    with ui.row().classes('w-full justify-between items-center border-b border-gray-800 py-1'):
                        ui.label(f"HD ({cls_name} {hd['die']})").classes('text-gray-400')
                        with ui.row().classes('items-center gap-1'):
                            render_pm_adjuster(_make_hd_adjust(cls_name))
                            ui.label(f"{hd['current']} / {hd['maximum']}").classes('text-white ml-2')

                if show_death_saves:
                    for ds_label, ds_field, ds_value in [
                        ("Death Saves — Successes", "death_save_successes", cs.death_save_successes),
                        ("Death Saves — Failures",  "death_save_failures",  cs.death_save_failures),
                    ]:
                        with ui.row().classes('w-full justify-between items-center border-b border-gray-800 py-1'):
                            ui.label(ds_label).classes('text-gray-400')
                            with ui.row().classes('items-center gap-1'):
                                filled = max(0, min(3, ds_value))
                                for i in range(3):
                                    is_checked = i < filled
                                    def _mk_handler(field=ds_field, idx=i):
                                        async def _h(e):
                                            cur = getattr(cs, field)
                                            new_val = idx + 1 if e.value else idx
                                            new_val = max(0, min(3, new_val))
                                            if new_val != cur:
                                                await _save({field: new_val})
                                        return _h
                                    ui.checkbox(value=is_checked, on_change=_mk_handler()).props('dense')

            with edit_col:
                hp_cur  = ui.number("Current HP", value=cs.hp_current, step=1).classes('w-full').props('dense')
                hp_max  = ui.number("Max HP", value=cs.hp_max, step=1, min=1).classes('w-full').props('dense')
                hp_temp = ui.number("Temp HP", value=cs.hp_temp, step=1, min=0).classes('w-full').props('dense')
                exh_inp = ui.number(exhaustion_label, value=cs.exhaustion, step=1, min=0, max=6).classes('w-full').props('dense')
                strife_inp = (
                    ui.number("Strife", value=cs.strife, step=1, min=0, max=6).classes('w-full').props('dense')
                    if show_strife else None
                )
                ds_succ_inp = (
                    ui.number("Death Save Successes", value=cs.death_save_successes, step=1, min=0, max=3).classes('w-full').props('dense')
                    if show_death_saves else None
                )
                ds_fail_inp = (
                    ui.number("Death Save Failures", value=cs.death_save_failures, step=1, min=0, max=3).classes('w-full').props('dense')
                    if show_death_saves else None
                )

                async def _save_hp():
                    updates = {
                        "hp_current": int(hp_cur.value or 0),
                        "hp_max":     int(hp_max.value or 1),
                        "hp_temp":    int(hp_temp.value or 0),
                        "exhaustion": int(exh_inp.value or 0),
                    }
                    if strife_inp is not None:
                        updates["strife"] = int(strife_inp.value or 0)
                    if ds_succ_inp is not None:
                        updates["death_save_successes"] = max(0, min(3, int(ds_succ_inp.value or 0)))
                    if ds_fail_inp is not None:
                        updates["death_save_failures"] = max(0, min(3, int(ds_fail_inp.value or 0)))
                    await _save(updates)

                ui.button("Save", on_click=_save_hp).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

    _section()
    return _section
