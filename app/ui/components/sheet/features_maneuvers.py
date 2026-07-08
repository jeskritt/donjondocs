"""Combat maneuvers sub-tab — used by the dispatcher in `features.py`.

Renders the Advanced 5e combat-maneuvers panel: tradition badges,
exertion tracker, and the per-maneuver list with add/edit dialogs.
The maneuver-system header (DC, attack bonus, exertion max, known
traditions) has its own edit dialog inside this module.

Each maneuver row toggles an extended view (label:value block + markdown
description, PHB-independent) on a whole-row click, matching the spell
list; the trailing edit/delete buttons sit outside the clickable area.
"""

from nicegui import ui

from app.schemas.char_sheet_specific import CharacterCombatManeuver
from app.ui.components.sheet.helpers import (
    render_detail_pairs,
    render_plain_markdown,
    toggle_element_display,
)
from app.ui.theme import DIALOG_CARD_STYLE, notify_error


def _render_maneuvers_tab(state, cs, maneuvers_data, maneuvers, _save):
    with ui.row().classes('w-full gap-4 items-center flex-wrap mb-1'):
        ui.label(f"Traditions: {maneuvers_data['known_traditions'] or '—'}").classes('text-gray-300 text-sm')
    with ui.row().classes('w-full gap-4 items-center flex-wrap mb-2'):
        ui.badge(f"DC {maneuvers_data['maneuver_dc']}", color='indigo').props('dense')
        ui.badge(f"Attack +{maneuvers_data['maneuver_attack']}", color='teal').props('dense')
        ui.label(f"Exertion: {maneuvers_data['exertion_current']} / {maneuvers_data['exertion_max']}").classes('text-white text-sm font-bold')

        async def _exertion_adjust(delta: int):
            new_val = max(0, min(cs.exertion_max, cs.exertion_current + delta))
            await _save({"exertion_current": new_val})

        ui.button(icon='remove', on_click=lambda: _exertion_adjust(-1)).props('flat round dense size=sm')
        ui.button(icon='add', on_click=lambda: _exertion_adjust(1)).props('flat round dense size=sm')
        ui.label(f"Known: {maneuvers_data['maneuvers_known']}").classes('text-gray-400 text-xs')
        ui.label(f"Max Degree: {maneuvers_data['max_degree']}").classes('text-gray-400 text-xs')

    def _open_edit_maneuver_header():
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
            ui.label("Edit Combat Maneuver Settings").classes('text-lg font-bold mb-2 text-white')
            inp_traditions = ui.input("Known Traditions (comma-separated)", value=cs.known_traditions).classes('w-full').props('dense')
            with ui.row().classes('w-full gap-2'):
                inp_ex_cur = ui.number("Exertion Current", value=cs.exertion_current, step=1).classes('flex-1').props('dense')
                inp_ex_max = ui.number("Exertion Max", value=cs.exertion_max, step=1).classes('flex-1').props('dense')
            with ui.row().classes('w-full gap-2'):
                inp_known = ui.number("Maneuvers Known", value=cs.maneuvers_known, step=1, min=0).classes('flex-1').props('dense')
                inp_deg   = ui.number("Max Degree", value=cs.max_degree, step=1, min=0).classes('flex-1').props('dense')
            with ui.row().classes('w-full gap-2'):
                inp_atk_misc = ui.number("Attack Misc", value=cs.maneuver_attack_misc, step=1).classes('flex-1').props('dense')
                inp_dc_misc  = ui.number("DC Misc", value=cs.maneuver_dc_misc, step=1).classes('flex-1').props('dense')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')
                async def _save_header():
                    await _save({
                        "known_traditions": (inp_traditions.value or "").strip(),
                        "exertion_current": int(inp_ex_cur.value or 0),
                        "exertion_max": int(inp_ex_max.value or 0),
                        "maneuvers_known": int(inp_known.value or 0),
                        "max_degree": int(inp_deg.value or 0),
                        "maneuver_attack_misc": int(inp_atk_misc.value or 0),
                        "maneuver_dc_misc": int(inp_dc_misc.value or 0),
                    })
                    dialog.close()
                ui.button("Save", on_click=_save_header).props('unelevated color=primary')
        dialog.open()

    ui.button(icon='edit', on_click=_open_edit_maneuver_header).props('flat round dense color=primary').classes('mb-2')

    if not maneuvers:
        ui.label("No combat maneuvers added yet.").classes('text-gray-500 italic text-sm py-2')
    else:
        sorted_maneuvers = sorted(maneuvers, key=lambda m: (m['degree'], m['name']))
        for m in sorted_maneuvers:
            mname = m['name']
            orig_idx = next(i for i, cm in enumerate(cs.combat_maneuvers) if cm.name == mname)
            with ui.column().classes('w-full gap-0'):
                with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                    # Whole info area toggles the extended view; the edit/delete
                    # buttons sit outside it so their clicks never reach the toggle.
                    info_row = ui.row().classes('flex-1 items-center gap-2 cursor-pointer no-wrap')
                    with info_row:
                        ui.label(str(m['degree'])).classes('w-6 text-center text-xs text-gray-400')
                        ui.label(mname).classes('text-white text-sm flex-1')
                        ui.label(m.get('tradition') or '—').classes('w-20 text-gray-400 text-xs')
                        ui.label(str(m.get('exertion_cost', 0))).classes('w-8 text-center text-gray-400 text-xs')
                        ui.label(m.get('action_type') or '—').classes('w-8 text-center text-gray-400 text-xs')
                        if m.get('stance'):
                            ui.icon('shield', size='xs').classes('text-amber-400')
                        else:
                            ui.label('').classes('w-4')
                    ui.button(icon='edit', on_click=lambda n=mname, i=orig_idx: _open_edit_maneuver(cs, _save, n, i)).props('flat round dense color=primary')
                    async def _rm_maneuver(n=mname):
                        updated = [cm for cm in cs.combat_maneuvers if cm.name != n]
                        await _save({"combat_maneuvers": [cm.model_dump() for cm in updated]})
                    ui.button(icon='delete', on_click=_rm_maneuver).props('flat round dense color=negative')
                desc_row = ui.column().classes('w-full pl-8 py-1 gap-1 border-b border-gray-800').style('display: none')
                with desc_row:
                    render_detail_pairs([
                        ("Degree", str(m['degree'])),
                        ("Tradition", m.get('tradition')),
                        ("Exertion Cost", str(m.get('exertion_cost', 0))),
                        ("Action Type", m.get('action_type')),
                        ("Stance", "Yes" if m.get('stance') else "No"),
                    ])
                    render_plain_markdown(m.get('description'))
                info_row.on('click', lambda dr=desc_row: toggle_element_display(dr))

    tradition_options = [t.strip() for t in cs.known_traditions.split(',') if t.strip()] if cs.known_traditions else []

    ui.button("Add Combat Maneuver", icon='add', on_click=lambda: _open_add_maneuver(cs, _save, tradition_options)).props('unelevated color=indigo').classes('mt-2')


def _open_add_maneuver(cs, _save, tradition_options):
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Add Combat Maneuver").classes('text-lg font-bold mb-2 text-white')
        inp_name    = ui.input("Name").classes('w-full')
        inp_degree  = ui.number("Degree", value=1, min=1, max=5, step=1).classes('w-full').props('dense')
        inp_trad    = ui.select(tradition_options + ["Other..."], label="Tradition", value=tradition_options[0] if tradition_options else None).classes('w-full')
        inp_trad_custom = ui.input("Custom Tradition").classes('w-full').props('dense').bind_visibility_from(inp_trad, 'value', value='Other...')
        with ui.row().classes('w-full gap-2'):
            inp_cost   = ui.number("Exertion Cost", value=0, min=0, step=1).classes('flex-1').props('dense')
            inp_action = ui.select(["A", "BA", "R"], label="Action Type", value="A").classes('flex-1').props('dense')
        inp_stance  = ui.checkbox("Stance")
        inp_desc    = ui.textarea("Description").classes('w-full').props('rows=3')
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')
            async def _confirm():
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                trad = inp_trad_custom.value.strip() if inp_trad.value == "Other..." else (inp_trad.value or "")
                entry = CharacterCombatManeuver(
                    name=name,
                    degree=int(inp_degree.value or 1),
                    tradition=trad,
                    exertion_cost=int(inp_cost.value or 0),
                    action_type=inp_action.value or "",
                    stance=bool(inp_stance.value),
                    description=(inp_desc.value or "").strip(),
                )
                updated = [cm.model_dump() for cm in cs.combat_maneuvers] + [entry.model_dump()]
                await _save({"combat_maneuvers": updated})
                dialog.close()
            ui.button("Add", on_click=_confirm).props('unelevated color=primary')
    dialog.open()


def _open_edit_maneuver(cs, _save, maneuver_name, maneuver_idx):
    man_obj = next((cm for cm in cs.combat_maneuvers if cm.name == maneuver_name), None)
    if not man_obj:
        return
    tradition_options = [t.strip() for t in cs.known_traditions.split(',') if t.strip()] if cs.known_traditions else []
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Edit Combat Maneuver").classes('text-lg font-bold mb-2 text-white')
        inp_name    = ui.input("Name", value=man_obj.name).classes('w-full')
        inp_degree  = ui.number("Degree", value=man_obj.degree, min=1, max=5, step=1).classes('w-full').props('dense')
        cur_trad = man_obj.tradition or ""
        trad_val = cur_trad if cur_trad in tradition_options else ("Other..." if cur_trad else (tradition_options[0] if tradition_options else None))
        inp_trad    = ui.select(tradition_options + ["Other..."], label="Tradition", value=trad_val).classes('w-full')
        inp_trad_custom = ui.input("Custom Tradition", value=cur_trad if trad_val == "Other..." else "").classes('w-full').props('dense').bind_visibility_from(inp_trad, 'value', value='Other...')
        with ui.row().classes('w-full gap-2'):
            inp_cost   = ui.number("Exertion Cost", value=man_obj.exertion_cost, min=0, step=1).classes('flex-1').props('dense')
            inp_action = ui.select(["A", "BA", "R"], label="Action Type", value=man_obj.action_type or "A").classes('flex-1').props('dense')
        inp_stance  = ui.checkbox("Stance", value=man_obj.stance)
        inp_desc    = ui.textarea("Description", value=man_obj.description or "").classes('w-full').props('rows=3')
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')
            async def _confirm(idx=maneuver_idx):
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                trad = inp_trad_custom.value.strip() if inp_trad.value == "Other..." else (inp_trad.value or "")
                entry = CharacterCombatManeuver(
                    name=name,
                    degree=int(inp_degree.value or 1),
                    tradition=trad,
                    exertion_cost=int(inp_cost.value or 0),
                    action_type=inp_action.value or "",
                    stance=bool(inp_stance.value),
                    description=(inp_desc.value or "").strip(),
                )
                updated = [cm.model_dump() for cm in cs.combat_maneuvers]
                updated[idx] = entry.model_dump()
                await _save({"combat_maneuvers": updated})
                dialog.close()
            ui.button("Save", on_click=_confirm).props('unelevated color=primary')
    dialog.open()
