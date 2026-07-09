from nicegui import ui

from app.ui.theme import DIALOG_CARD_STYLE, notify_error
from app.ui.components.sheet.helpers import _PROF_ICONS, _fmt_bonus, make_toggle_handler
from app.schemas.char_sheet_specific import CharacterSkillSimple
from app.services.session import service_session
from app.services.global_items_service import list_skills


def _render_skills(state, char_id, user, _save):
    if not state["vd"].get("style_flags", {}).get("has_skills", True):
        return

    @ui.refreshable
    def _section():
        skills = state["vd"].get("skills", [])
        is_editing = [False]
        skill_prof = {}
        skill_misc = {}
        skill_notes = {}

        with ui.card().classes('w-full flex-1 min-w-[260px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Skills").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            display_col = ui.column().classes('w-full')
            edit_col = ui.column().classes('w-full')

            with display_col:
                if not skills:
                    ui.label("No skills added yet.").classes('text-gray-500 italic text-sm py-2')
                with ui.column().classes('w-full gap-0').style('max-height: 360px; overflow-y: auto;'):
                    for s in skills:
                        icon, color = _PROF_ICONS.get(s['proficiency'], ("○", "text-gray-500"))
                        with ui.row().classes('w-full justify-between border-b border-gray-800 py-1 items-center'):
                            ui.label(icon).classes(f'{color} w-5 text-center')
                            with ui.column().classes('flex-1 gap-0'):
                                ui.label(s['name']).classes('text-gray-300')
                                if s.get('notes'):
                                    ui.label(s['notes']).classes('text-gray-500 text-xs italic')
                            ui.label(s['attribute']).classes('text-gray-500 text-xs w-10')
                            ui.label(_fmt_bonus(s['total'])).classes('text-white text-right')

            with edit_col:
                if not skills:
                    ui.label("No skills. Use Add Skill below.").classes('text-gray-500 italic text-sm py-2')
                with ui.column().classes('w-full gap-0').style('max-height: 360px; overflow-y: auto;'):
                    for s in skills:
                        skill_prof[s['name']] = [s['proficiency']]
                        with ui.column().classes('w-full border-b border-gray-800 py-1 gap-1'):
                            with ui.row().classes('w-full items-center gap-2'):
                                si, sc = _PROF_ICONS[s['proficiency']]
                                badge = ui.label(si).classes(f'{sc} w-6 text-center cursor-pointer text-lg')
                                name = s['name']

                                def _make_cycle(b, n):
                                    def _c():
                                        skill_prof[n][0] = (skill_prof[n][0] + 1) % 4
                                        ni, nc = _PROF_ICONS[skill_prof[n][0]]
                                        b.text = ni
                                        b.classes(replace=f'{nc} w-6 text-center cursor-pointer text-lg')
                                        b.update()
                                    return _c

                                badge.on('click', _make_cycle(badge, name))
                                ui.label(s['name']).classes('text-gray-300 flex-1 text-sm')
                                skill_misc[s['name']] = ui.number('Misc', value=s['misc'], step=1).classes('w-20').props('dense')

                                async def _remove(sname=name):
                                    updated = [sk for sk in state["cs"].skills if sk.name != sname]
                                    await _save({"skills": [sk.model_dump() for sk in updated]})

                                ui.button(icon='delete', on_click=_remove).props('flat round dense color=negative')
                            skill_notes[s['name']] = ui.input(
                                'Notes', value=s.get('notes') or ''
                            ).classes('w-full').props('dense')

                async def _save_skills():
                    by_name = {sk.name: sk for sk in state["cs"].skills}
                    updated = []
                    for sk in state["cs"].skills:
                        note_el = skill_notes.get(sk.name)
                        note_val = (note_el.value if note_el else sk.notes) or ""
                        updated.append({
                            "name": sk.name,
                            "attribute": sk.attribute,
                            "proficiency": skill_prof.get(sk.name, [sk.proficiency])[0],
                            "misc": int((skill_misc.get(sk.name) or type('o', (), {'value': sk.misc})()).value or 0),
                            "example_uses": by_name[sk.name].example_uses,
                            "notes": note_val.strip() or None,
                        })
                    await _save({"skills": updated})

                ui.button("Save", on_click=_save_skills).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

            ui.separator()

            async def _open_add_skill():
                cs = state["cs"]
                _ATTRS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
                if cs.vigor_enabled:
                    _ATTRS = _ATTRS + ["VIG"]
                async with service_session() as session:
                    global_skills = await list_skills(session, cs.style, owner_id=user.id)

                skill_map = {
                    gs.name: (gs.attribute or "STR", gs.example_uses)
                    for gs in global_skills
                }
                existing = {sk.name for sk in cs.skills}
                available_names = [n for n in skill_map.keys() if n not in existing]

                with ui.dialog() as dialog, ui.card().classes('w-full max-w-sm').style(DIALOG_CARD_STYLE):
                    ui.label("Add Skill").classes('text-lg font-bold mb-2 text-white')
                    skill_select = ui.select(
                        options=available_names + ["Custom…"],
                        label="Skill",
                        value=available_names[0] if available_names else "Custom…",
                    ).classes('w-full')
                    custom_name = ui.input("Custom Name").classes('w-full').bind_visibility_from(skill_select, 'value', lambda v: v == "Custom…")
                    first_attr = skill_map[available_names[0]][0] if available_names else "STR"
                    attr_select = ui.select(options=_ATTRS, label="Attribute", value=first_attr).classes('w-full')
                    help_label = ui.label(
                        (skill_map[available_names[0]][1] or "")
                        if available_names else ""
                    ).classes('text-xs text-gray-400 mt-1')
                    notes_input = ui.textarea("Notes (optional)").classes('w-full').props('rows=2 dense')

                    def _on_change(e):
                        entry = skill_map.get(e.value)
                        if entry:
                            attr_select.value = entry[0]
                            help_label.text = entry[1] or ""
                        else:
                            help_label.text = ""
                    skill_select.on_value_change(_on_change)

                    with ui.row().classes('w-full justify-end gap-2 mt-4'):
                        ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

                        async def _confirm():
                            picked = skill_select.value
                            if picked == "Custom…":
                                name = (custom_name.value or "").strip()
                                example_uses = None
                            else:
                                name = picked
                                example_uses = skill_map.get(name, (None, None))[1]
                            if not name:
                                notify_error("Skill name required")
                                return
                            new_sk = CharacterSkillSimple(
                                name=name,
                                attribute=attr_select.value,
                                proficiency=0,
                                misc=0,
                                example_uses=example_uses,
                                notes=(notes_input.value or "").strip() or None,
                            )
                            updated = [sk.model_dump() for sk in state["cs"].skills] + [new_sk.model_dump()]
                            await _save({"skills": updated})
                            dialog.close()

                        ui.button("Add", on_click=_confirm).props('unelevated color=primary')
                dialog.open()

            ui.button("Add Skill", icon='add', on_click=_open_add_skill).props('flat dense').classes('text-indigo-400 mt-1')

    _section()
    return _section
