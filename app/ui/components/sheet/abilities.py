from nicegui import ui

from app.ui.components.sheet.helpers import _PROF_ICONS, _fmt_bonus, make_toggle_handler


def _render_abilities(state, char_id, user, _save):

    @ui.refreshable
    def _section():
        attrs = state["vd"].get("attributes", [])
        is_editing = [False]
        score_inputs = {}
        save_prof_state = {}
        save_misc_inputs = {}

        with ui.card().classes('w-full flex-[2] min-w-[380px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Abilities & Saves").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            with ui.row().classes('w-full px-1 mb-1'):
                ui.label('').classes('w-10')
                ui.label('Score').classes('text-xs text-gray-500 w-12 text-center')
                ui.label('Mod').classes('text-xs text-gray-500 w-12 text-center')
                ui.label('Save').classes('text-xs text-gray-500 flex-1 text-center')

            display_col = ui.column().classes('w-full')
            edit_col = ui.column().classes('w-full')

            with display_col:
                for a in attrs:
                    si, sc = _PROF_ICONS.get(a['save_proficiency'], ("○", "text-gray-500"))
                    with ui.row().classes('w-full justify-between border-b border-gray-800 py-1 items-center'):
                        ui.label(a['label']).classes('font-bold text-gray-300 w-10')
                        ui.label(str(a['total'])).classes('text-white w-12 text-center')
                        ui.label(_fmt_bonus(a['modifier'])).classes('text-gray-400 text-sm w-12 text-center')
                        with ui.row().classes('flex-1 justify-center items-center gap-2'):
                            ui.label(si).classes(f'{sc} text-sm')
                            ui.label(_fmt_bonus(a['save_total'])).classes('text-white text-sm')

            key_map = {"STR": "str_score", "DEX": "dex_score", "CON": "con_score",
                       "INT": "int_score", "WIS": "wis_score", "CHA": "cha_score"}

            with edit_col:
                ui.label("Score Breakdown").classes('text-xs text-gray-500 mb-1')
                for a in attrs:
                    key = a['label']
                    save_prof_state[key] = [a['save_proficiency']]
                    ui.label(key).classes('font-bold text-gray-400 text-sm mt-2')
                    with ui.row().classes('w-full gap-1 items-end'):
                        score_inputs[f"{key}_base"]   = ui.number('Base',  value=a['base'],   min=3, max=24, step=1).classes('flex-1').props('dense')
                        score_inputs[f"{key}_racial"] = ui.number('Race',  value=a['racial'], step=1).classes('flex-1').props('dense')
                        score_inputs[f"{key}_level"]  = ui.number('ASI',   value=a['level'],  step=1).classes('flex-1').props('dense')
                        score_inputs[f"{key}_misc"]   = ui.number('Misc',  value=a['misc'],   step=1).classes('flex-1').props('dense')

                        si, sc = _PROF_ICONS[save_prof_state[key][0]]
                        save_badge = ui.label(si).classes(f'{sc} w-6 text-center cursor-pointer text-lg ml-2')

                        def _make_cycle(badge_el, attr_key):
                            def _cycle():
                                save_prof_state[attr_key][0] = (save_prof_state[attr_key][0] + 1) % 4
                                ni, nc = _PROF_ICONS[save_prof_state[attr_key][0]]
                                badge_el.text = ni
                                badge_el.classes(replace=f'{nc} w-6 text-center cursor-pointer text-lg ml-2')
                                badge_el.update()
                            return _cycle

                        save_badge.on('click', _make_cycle(save_badge, key))
                        save_misc_inputs[key] = ui.number('Save+', value=a['save_misc'], step=1).classes('w-14').props('dense')

                async def _save_abilities():
                    score_updates = {}
                    new_saves = []
                    for label, field in key_map.items():
                        score_updates[field] = {
                            "base":   int(score_inputs[f"{label}_base"].value   or 10),
                            "racial": int(score_inputs[f"{label}_racial"].value or 0),
                            "level":  int(score_inputs[f"{label}_level"].value  or 0),
                            "misc":   int(score_inputs[f"{label}_misc"].value   or 0),
                        }
                        new_saves.append({
                            "attribute":   label,
                            "proficiency": save_prof_state[label][0],
                            "misc":        int(save_misc_inputs[label].value or 0),
                        })
                    score_updates["saving_throws"] = new_saves
                    await _save(score_updates)

                ui.button("Save", on_click=_save_abilities).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

    _section()
    return _section
