"""Magic & spells sub-tab — used by the dispatcher in `features.py`.

Renders magic resources (slots / per-level / points / Shadowdark
casting), an optional extra-resource tracker per resource (e.g.
Sorcery Points), and the spell list with add/edit dialogs.
"""

from nicegui import ui

from app.schemas.char_sheet_global import MagicType
from app.schemas.char_sheet_specific import (
    CharacterSpell,
    ExtraResource,
    MagicResource,
)
from app.ui.components.sheet.helpers import _fmt_bonus, _render_slot_checkboxes
from app.ui.theme import DIALOG_CARD_STYLE, notify_error


def _render_magic_tab(state, cs, magic, _save):
    resources = magic.get("resources", [])
    spells = magic.get("spells", [])

    if not resources:
        ui.label("No magic resources yet. Add one to start tracking spells.").classes('text-gray-500 italic text-sm py-2')

    for r in resources:
        with ui.expansion(f"{r['name']} ({r['magic_type']})", icon='auto_awesome').classes('w-full border border-gray-700 rounded mb-1'):
            with ui.row().classes('gap-6 text-sm'):
                ui.label(f"Attribute: {r['attribute'] or '—'}").classes('text-gray-400')
                ui.label(f"Attack: {_fmt_bonus(r['spell_attack_total'])}").classes('text-white')
                ui.label(f"Save DC: {r['spell_dc_total']}").classes('text-white')

            rname = r['name']
            cur_list = r['current']
            max_list = r['maximum']
            mtype = r['magic_type']

            if isinstance(cur_list, list) and isinstance(max_list, list):
                if mtype == MagicType.POINTS.value:
                    ui.label(f"Points: {cur_list[0] if cur_list else 0} / {max_list[0] if max_list else 0}").classes('text-gray-300 text-sm mt-1')
                else:
                    _render_slot_checkboxes(cs, rname, cur_list, max_list, mtype, _save)

                async def _reset_resource(n=rname):
                    updated = []
                    for mr in cs.magic_resources:
                        d = mr.model_dump()
                        if mr.name == n and isinstance(d.get("maximum"), list):
                            d["current"] = list(d["maximum"])
                        updated.append(d)
                    await _save({"magic_resources": updated})
                ui.button("Reset", icon='restart_alt', on_click=_reset_resource
                          ).props('flat dense').classes('text-indigo-400 mt-1')

            er = r.get('extra_resource')
            if er:
                _RESET_LABELS = {"short": "Short rest", "long": "Long rest", "none": "Manual"}
                with ui.row().classes('w-full items-center gap-2 mt-1 border border-gray-700 rounded px-2 py-1'):
                    ui.label(f"{er['name']}:").classes('text-gray-400 text-sm')
                    ui.label(f"{er['current']} / {er['maximum']}").classes('text-white text-sm font-bold')
                    ui.label(f"({_RESET_LABELS.get(er['reset_on'], 'Manual')})").classes('text-gray-500 text-xs')

                    er_rname = rname

                    async def _er_adjust(delta: int, n=er_rname):
                        updated = []
                        for mr in cs.magic_resources:
                            d = mr.model_dump()
                            if mr.name == n and d.get("extra_resource"):
                                d["extra_resource"]["current"] = max(0, min(
                                    d["extra_resource"]["maximum"],
                                    d["extra_resource"]["current"] + delta,
                                ))
                            updated.append(d)
                        await _save({"magic_resources": updated})

                    ui.button(icon='remove', on_click=lambda n=er_rname: _er_adjust(-1, n)).props('flat round dense size=sm')
                    ui.button(icon='add', on_click=lambda n=er_rname: _er_adjust(1, n)).props('flat round dense size=sm')

            with ui.row().classes('gap-1 mt-1'):
                ui.button("Edit", icon='edit', on_click=lambda n=rname: _open_edit_resource(cs, _save, n)).props('flat dense color=primary')

                async def _rm_resource(n=rname):
                    updated = [mr for mr in cs.magic_resources if mr.name != n]
                    await _save({"magic_resources": [mr.model_dump() for mr in updated]})
                ui.button("Remove", icon='delete', on_click=_rm_resource).props('flat dense color=negative')

    ui.button("Add Magic Resource", icon='add', on_click=lambda: _open_add_resource(cs, _save, resources)).props('unelevated color=indigo').classes('mt-2')

    if resources or spells:
        ui.separator()
        ui.label("Spells").classes('text-sm text-gray-400 mt-2 mb-1')
        if not spells:
            ui.label("No spells added yet.").classes('text-gray-500 italic text-sm py-1')
        else:
            sorted_spells = sorted(spells, key=lambda s: (s['level'], s['name']))
            for sp_idx, sp in enumerate(sorted_spells):
                orig_idx = spells.index(sp)
                sp_name = sp['name']
                desc_row = None
                with ui.column().classes('w-full gap-0'):
                    with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                        level_lbl = "C" if sp['level'] == 0 else str(sp['level'])
                        ui.label(level_lbl).classes('w-6 text-center text-xs text-gray-400')
                        name_classes = 'text-sm'
                        name_classes += ' text-white font-bold' if sp.get('prepared') else ' text-gray-300'
                        def _toggle_sp_desc(dr=None):
                            if dr:
                                vis = dr.style.get('display', 'none') != 'none'
                                dr.style('display: none' if vis else 'display: block')
                        name_btn = ui.button(sp_name, on_click=lambda: None).props('flat dense no-caps').classes(name_classes + ' flex-1 justify-start')
                        if sp.get('ritual'):
                            ui.badge('R', color='purple').props('dense')
                        ui.label(sp.get('casting_time') or '—').classes('w-20 text-gray-400 text-xs')
                        ui.label(sp.get('spell_range') or '—').classes('w-16 text-gray-400 text-xs')
                        dur = sp.get('duration') or ''
                        dur_display = f"Conc. {dur}" if sp.get('concentration') and dur else ('Conc.' if sp.get('concentration') else dur or '—')
                        ui.label(dur_display).classes('w-24 text-gray-400 text-xs')
                        ui.label(sp.get('resource_name') or '—').classes('flex-1 text-gray-400 text-sm')
                        ui.button(icon='edit', on_click=lambda n=sp_name, i=orig_idx: _open_edit_spell(cs, _save, resources, n, i)).props('flat round dense color=primary')
                        async def _rm_spell(n=sp_name):
                            updated = [s for s in cs.spells if s.name != n]
                            await _save({"spells": [s.model_dump() for s in updated]})
                        ui.button(icon='delete', on_click=_rm_spell).props('flat round dense color=negative')
                    desc_row = ui.row().classes('w-full pl-8 py-1 border-b border-gray-800').style('display: none')
                    with desc_row:
                        ui.label(sp.get('description') or 'No description.').classes('text-gray-400 text-sm whitespace-pre-wrap')
                    name_btn.on('click', lambda dr=desc_row: _toggle_sp_desc(dr))

        ui.button("Add Spell", icon='add', on_click=lambda: _open_add_spell(cs, _save, resources)).props('unelevated color=indigo').classes('mt-2')


def _open_add_resource(cs, _save, resources):
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Add Magic Resource").classes('text-lg font-bold mb-2 text-white')
        inp_name = ui.input("Name", value="Spellcasting").classes('w-full')
        inp_src  = ui.input("Source (class/feat/item)").classes('w-full')
        inp_type = ui.select([t.value for t in MagicType], label="Magic Type", value=MagicType.PERLEVEL.value).classes('w-full')
        inp_attr = ui.select(["STR","DEX","CON","INT","WIS","CHA", None], label="Attribute", value="INT").classes('w-full')
        with ui.row().classes('w-full gap-2'):
            inp_atk_misc = ui.number("Attack Misc", value=0, step=1).classes('flex-1').props('dense')
            inp_dc_misc  = ui.number("DC Misc",    value=0, step=1).classes('flex-1').props('dense')
        inp_slots = ui.input("Slots (comma-separated, e.g. 4,2)", value="").classes('w-full')
        ui.label("SLOTS: one entry. PERLEVEL: per level. SHADOWDARK/POINTS: leave blank or single.").classes('text-xs text-gray-500')

        er_check = ui.checkbox("Add extra resource tracker (e.g. Sorcery Points)")
        er_container = ui.column().classes('w-full pl-4')
        er_container.set_visibility(False)
        with er_container:
            er_name = ui.input("Resource Name", placeholder="Sorcery Points").classes('w-full').props('dense')
            with ui.row().classes('w-full gap-2 items-center'):
                er_max = ui.number("Maximum", value=0, step=1, min=0).classes('flex-1').props('dense')
                er_reset = ui.select(["short", "long", "none"], label="Recharges on", value="long").classes('flex-1').props('dense')

        def _toggle_er():
            er_container.set_visibility(er_check.value)
        er_check.on_value_change(_toggle_er)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm():
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                raw = inp_slots.value.strip()
                slots = None
                if raw:
                    try:
                        slots = [int(x.strip()) for x in raw.split(",") if x.strip()]
                    except ValueError:
                        notify_error("Slots must be numbers"); return
                mt = MagicType(inp_type.value)
                extra = None
                if er_check.value:
                    er_n = (er_name.value or "").strip()
                    if not er_n:
                        notify_error("Resource name required"); return
                    er_m = max(0, int(er_max.value or 0))
                    extra = ExtraResource(
                        name=er_n,
                        current=er_m,
                        maximum=er_m,
                        reset_on=er_reset.value,
                    )
                entry = MagicResource(
                    name=name,
                    source=(inp_src.value or "").strip(),
                    magic_type=mt,
                    attribute=inp_attr.value,
                    spell_attack_misc=int(inp_atk_misc.value or 0),
                    spell_dc_misc=int(inp_dc_misc.value or 0),
                    current=slots,
                    maximum=slots,
                    extra_resource=extra,
                )
                updated = [mr.model_dump() for mr in cs.magic_resources] + [entry.model_dump()]
                await _save({"magic_resources": updated})
                dialog.close()

            ui.button("Add", on_click=_confirm).props('unelevated color=primary')
    dialog.open()


def _open_edit_resource(cs, _save, resource_name):
    res_obj = next((mr for mr in cs.magic_resources if mr.name == resource_name), None)
    if not res_obj:
        return
    res_idx = next(i for i, mr in enumerate(cs.magic_resources) if mr.name == resource_name)
    old_max = res_obj.maximum
    old_slots_str = ",".join(str(x) for x in old_max) if isinstance(old_max, list) else ""
    has_er = res_obj.extra_resource is not None

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Edit Magic Resource").classes('text-lg font-bold mb-2 text-white')
        inp_name = ui.input("Name", value=res_obj.name).classes('w-full')
        inp_src  = ui.input("Source (class/feat/item)", value=res_obj.source or "").classes('w-full')
        inp_type = ui.select([t.value for t in MagicType], label="Magic Type", value=res_obj.magic_type.value if hasattr(res_obj.magic_type, 'value') else res_obj.magic_type).classes('w-full')
        inp_attr = ui.select(["STR","DEX","CON","INT","WIS","CHA", None], label="Attribute", value=res_obj.attribute).classes('w-full')
        with ui.row().classes('w-full gap-2'):
            inp_atk_misc = ui.number("Attack Misc", value=res_obj.spell_attack_misc, step=1).classes('flex-1').props('dense')
            inp_dc_misc  = ui.number("DC Misc", value=res_obj.spell_dc_misc, step=1).classes('flex-1').props('dense')
        inp_slots = ui.input("Slots (comma-separated, e.g. 4,2)", value=old_slots_str).classes('w-full')
        ui.label("SLOTS: one entry. PERLEVEL: per level. SHADOWDARK/POINTS: leave blank or single.").classes('text-xs text-gray-500')

        er_check = ui.checkbox("Extra resource tracker", value=has_er)
        er_container = ui.column().classes('w-full pl-4')
        er_container.set_visibility(has_er)
        with er_container:
            er_name = ui.input("Resource Name", value=res_obj.extra_resource.name if has_er else "", placeholder="Sorcery Points").classes('w-full').props('dense')
            with ui.row().classes('w-full gap-2 items-center'):
                er_max = ui.number("Maximum", value=res_obj.extra_resource.maximum if has_er else 0, step=1, min=0).classes('flex-1').props('dense')
                er_reset = ui.select(["short", "long", "none"], label="Recharges on", value=res_obj.extra_resource.reset_on if has_er else "long").classes('flex-1').props('dense')

        def _toggle_er():
            er_container.set_visibility(er_check.value)
        er_check.on_value_change(_toggle_er)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm(idx=res_idx):
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                raw = inp_slots.value.strip()
                new_slots = None
                if raw:
                    try:
                        new_slots = [int(x.strip()) for x in raw.split(",") if x.strip()]
                    except ValueError:
                        notify_error("Slots must be numbers"); return
                mt = MagicType(inp_type.value)
                extra = None
                if er_check.value:
                    er_n = (er_name.value or "").strip()
                    if not er_n:
                        notify_error("Resource name required"); return
                    er_m = max(0, int(er_max.value or 0))
                    old_er = res_obj.extra_resource
                    er_cur = old_er.current if old_er and old_er.maximum == er_m else er_m
                    extra = ExtraResource(
                        name=er_n,
                        current=er_cur,
                        maximum=er_m,
                        reset_on=er_reset.value,
                    )
                cur_slots = new_slots if new_slots != old_max else res_obj.current
                entry = MagicResource(
                    name=name,
                    source=(inp_src.value or "").strip(),
                    magic_type=mt,
                    attribute=inp_attr.value,
                    spell_attack_misc=int(inp_atk_misc.value or 0),
                    spell_dc_misc=int(inp_dc_misc.value or 0),
                    current=cur_slots,
                    maximum=new_slots,
                    extra_resource=extra,
                )
                updated = [mr.model_dump() for mr in cs.magic_resources]
                updated[idx] = entry.model_dump()
                await _save({"magic_resources": updated})
                dialog.close()

            ui.button("Save", on_click=_confirm).props('unelevated color=primary')
    dialog.open()


def _open_add_spell(cs, _save, resources):
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Add Spell").classes('text-lg font-bold mb-2 text-white')
        inp_name   = ui.input("Name").classes('w-full')
        inp_level  = ui.number("Level (0=cantrip)", value=0, min=0, max=9, step=1).classes('w-full').props('dense')
        inp_desc   = ui.textarea("Description").classes('w-full').props('rows=3')
        inp_cast   = ui.input("Casting Time").classes('w-full').props('dense')
        with ui.row().classes('w-full gap-2'):
            inp_range  = ui.input("Range").classes('flex-1').props('dense')
            inp_dur    = ui.input("Duration").classes('flex-1').props('dense')
        with ui.row().classes('w-full gap-4'):
            inp_ritual = ui.checkbox("Ritual")
            inp_conc   = ui.checkbox("Concentration")
        resource_names = [r['name'] for r in resources]
        inp_res    = ui.select(resource_names + [None], label="Resource", value=resource_names[0] if resource_names else None).classes('w-full')
        inp_prep   = ui.checkbox("Prepared")

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm():
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                entry = CharacterSpell(
                    name=name,
                    level=int(inp_level.value or 0),
                    description=(inp_desc.value or "").strip(),
                    casting_time=(inp_cast.value or "").strip(),
                    spell_range=(inp_range.value or "").strip(),
                    duration=(inp_dur.value or "").strip(),
                    ritual=bool(inp_ritual.value),
                    concentration=bool(inp_conc.value),
                    resource_name=inp_res.value,
                    prepared=bool(inp_prep.value),
                )
                updated = [s.model_dump() for s in cs.spells] + [entry.model_dump()]
                await _save({"spells": updated})
                dialog.close()

            ui.button("Add", on_click=_confirm).props('unelevated color=primary')
    dialog.open()


def _open_edit_spell(cs, _save, resources, spell_name, spell_idx):
    spell_obj = next((s for s in cs.spells if s.name == spell_name), None)
    if not spell_obj:
        return
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Edit Spell").classes('text-lg font-bold mb-2 text-white')
        inp_name   = ui.input("Name", value=spell_obj.name).classes('w-full')
        inp_level  = ui.number("Level (0=cantrip)", value=spell_obj.level, min=0, max=9, step=1).classes('w-full').props('dense')
        inp_desc   = ui.textarea("Description", value=spell_obj.description or "").classes('w-full').props('rows=3')
        inp_cast   = ui.input("Casting Time", value=spell_obj.casting_time or "").classes('w-full').props('dense')
        with ui.row().classes('w-full gap-2'):
            inp_range  = ui.input("Range", value=spell_obj.spell_range or "").classes('flex-1').props('dense')
            inp_dur    = ui.input("Duration", value=spell_obj.duration or "").classes('flex-1').props('dense')
        with ui.row().classes('w-full gap-4'):
            inp_ritual = ui.checkbox("Ritual", value=spell_obj.ritual)
            inp_conc   = ui.checkbox("Concentration", value=spell_obj.concentration)
        resource_names = [r['name'] for r in resources]
        inp_res    = ui.select(resource_names + [None], label="Resource", value=spell_obj.resource_name).classes('w-full')
        inp_prep   = ui.checkbox("Prepared", value=spell_obj.prepared)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm(idx=spell_idx):
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                entry = CharacterSpell(
                    name=name,
                    level=int(inp_level.value or 0),
                    description=(inp_desc.value or "").strip(),
                    casting_time=(inp_cast.value or "").strip(),
                    spell_range=(inp_range.value or "").strip(),
                    duration=(inp_dur.value or "").strip(),
                    ritual=bool(inp_ritual.value),
                    concentration=bool(inp_conc.value),
                    resource_name=inp_res.value,
                    prepared=bool(inp_prep.value),
                )
                updated = [s.model_dump() for s in cs.spells]
                updated[idx] = entry.model_dump()
                await _save({"spells": updated})
                dialog.close()

            ui.button("Save", on_click=_confirm).props('unelevated color=primary')
    dialog.open()
