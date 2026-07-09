from nicegui import ui

from app.ui.theme import DIALOG_CARD_STYLE, notify_error
from app.ui.components.sheet.helpers import _PROF_ICONS, _fmt_bonus, make_toggle_handler
from app.schemas.char_sheet_specific import CharacterAction

_ATTRS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


def _render_actions(state, char_id, user, _save):

    @ui.refreshable
    def _section():
        actions = state["vd"].get("actions", [])
        cs = state["cs"]
        is_editing = [False]

        with ui.card().classes('w-full flex-1 min-w-[280px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Actions").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            display_col = ui.column().classes('w-full').style('max-height: 400px; overflow-y: auto;')
            edit_col = ui.column().classes('w-full').style('max-height: 400px; overflow-y: auto;')

            with display_col:
                if not actions:
                    ui.label("No actions added yet.").classes('text-gray-500 italic text-sm py-2')
                for a in actions:
                    with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                        prof_icon, prof_color = _PROF_ICONS[2 if a['proficient'] else 0]
                        ui.label(prof_icon).classes(f'{prof_color} w-5 text-center')
                        with ui.column().classes('flex-1 gap-0'):
                            ui.label(a['name']).classes('text-white text-sm font-bold')
                            sub_parts = []
                            if a['damage']:
                                sub_parts.append(a['damage'])
                            if a['range']:
                                sub_parts.append(a['range'])
                            if sub_parts:
                                ui.label(' • '.join(sub_parts)).classes('text-gray-400 text-xs')
                        if a.get('show_attack_bonus') and a.get('attack_bonus') is not None:
                            with ui.column().classes('items-center gap-0 w-12'):
                                ui.label('ATK').classes('text-xs text-gray-500')
                                ui.label(_fmt_bonus(a['attack_bonus'])).classes('text-white text-sm')
                        if a.get('show_attack_dc') and a.get('attack_dc') is not None:
                            with ui.column().classes('items-center gap-0 w-12'):
                                ui.label('DC').classes('text-xs text-gray-500')
                                ui.label(str(a['attack_dc'])).classes('text-white text-sm')

            with edit_col:
                if not cs.actions:
                    ui.label("No actions yet. Use Add Action below.").classes('text-gray-500 italic text-sm py-2')
                for idx, act in enumerate(cs.actions):
                    aname = act.name
                    with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-1'):
                        ui.label(aname).classes('flex-1 text-gray-300 text-sm')

                        ui.button(icon='edit', on_click=lambda a=act, i=idx: _open_edit_action(a, i)).props('flat round dense color=primary')

                        async def _remove(n=aname):
                            updated = [a for a in cs.actions if a.name != n]
                            await _save({"actions": [a.model_dump() for a in updated]})

                        ui.button(icon='delete', on_click=_remove).props('flat round dense color=negative')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

            ui.separator()

            def _open_add_action():
                with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
                    ui.label("Add Action").classes('text-lg font-bold mb-2 text-white')
                    inp_name    = ui.input("Name").classes('w-full').props('dense')
                    inp_attr    = ui.select(["—"] + _ATTRS + (["VIG"] if state["vd"].get("vigor_enabled") else []), label="Attribute", value="—").classes('w-full')
                    inp_prof    = ui.checkbox("Proficient")
                    inp_dmg     = ui.input("Damage (e.g. 1d8 slashing)").classes('w-full').props('dense')
                    inp_range   = ui.input("Range (e.g. 5 ft or 20/60)").classes('w-full').props('dense')
                    inp_atkmisc = ui.number("Attack misc", value=0, step=1).classes('w-full').props('dense')
                    inp_dcmisc  = ui.number("DC misc", value=0, step=1).classes('w-full').props('dense')
                    show_atk    = ui.checkbox("Show attack bonus", value=True)
                    show_dc     = ui.checkbox("Show attack DC", value=False)
                    inp_notes   = ui.textarea("Notes").classes('w-full').props('rows=2')

                    with ui.row().classes('w-full justify-end gap-2 mt-4'):
                        ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

                        async def _confirm():
                            name = (inp_name.value or "").strip()
                            if not name:
                                notify_error("Action name required"); return
                            new = CharacterAction(
                                name=name,
                                attribute=None if inp_attr.value == "—" else inp_attr.value,
                                proficient=bool(inp_prof.value),
                                attack_misc=int(inp_atkmisc.value or 0),
                                dc_misc=int(inp_dcmisc.value or 0),
                                show_attack_bonus=bool(show_atk.value),
                                show_attack_dc=bool(show_dc.value),
                                damage=(inp_dmg.value or "").strip(),
                                range=(inp_range.value or "").strip(),
                                notes=(inp_notes.value or "").strip(),
                            )
                            updated = [a.model_dump() for a in cs.actions] + [new.model_dump()]
                            await _save({"actions": updated})
                            dialog.close()

                        ui.button("Add", on_click=_confirm).props('unelevated color=primary')
                dialog.open()

            def _open_edit_action(act_obj, act_idx):
                with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
                    ui.label("Edit Action").classes('text-lg font-bold mb-2 text-white')
                    inp_name    = ui.input("Name", value=act_obj.name).classes('w-full').props('dense')
                    inp_attr    = ui.select(["—"] + _ATTRS + (["VIG"] if state["vd"].get("vigor_enabled") else []), label="Attribute", value=act_obj.attribute or "—").classes('w-full')
                    inp_prof    = ui.checkbox("Proficient", value=act_obj.proficient)
                    inp_dmg     = ui.input("Damage (e.g. 1d8 slashing)", value=act_obj.damage).classes('w-full').props('dense')
                    inp_range   = ui.input("Range (e.g. 5 ft or 20/60)", value=act_obj.range).classes('w-full').props('dense')
                    inp_atkmisc = ui.number("Attack misc", value=act_obj.attack_misc, step=1).classes('w-full').props('dense')
                    inp_dcmisc  = ui.number("DC misc", value=act_obj.dc_misc, step=1).classes('w-full').props('dense')
                    show_atk    = ui.checkbox("Show attack bonus", value=act_obj.show_attack_bonus)
                    show_dc     = ui.checkbox("Show attack DC", value=act_obj.show_attack_dc)
                    inp_notes   = ui.textarea("Notes", value=act_obj.notes).classes('w-full').props('rows=2')

                    with ui.row().classes('w-full justify-end gap-2 mt-4'):
                        ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

                        async def _confirm(i=act_idx):
                            name = (inp_name.value or "").strip()
                            if not name:
                                notify_error("Action name required"); return
                            new = CharacterAction(
                                name=name,
                                attribute=None if inp_attr.value == "—" else inp_attr.value,
                                proficient=bool(inp_prof.value),
                                attack_misc=int(inp_atkmisc.value or 0),
                                dc_misc=int(inp_dcmisc.value or 0),
                                show_attack_bonus=bool(show_atk.value),
                                show_attack_dc=bool(show_dc.value),
                                damage=(inp_dmg.value or "").strip(),
                                range=(inp_range.value or "").strip(),
                                notes=(inp_notes.value or "").strip(),
                            )
                            updated = [a.model_dump() for a in cs.actions]
                            updated[i] = new.model_dump()
                            await _save({"actions": updated})
                            dialog.close()

                        ui.button("Save", on_click=_confirm).props('unelevated color=primary')
                dialog.open()

            ui.button("Add Action", icon='add', on_click=_open_add_action).props('flat dense').classes('text-indigo-400 mt-1')

    _section()
    return _section
