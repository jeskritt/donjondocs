"""Magic & spells sub-tab — used by the dispatcher in `features.py`.

Renders magic resources (slots / per-level / points / Shadowdark /
Ultramodern5 DARK casting), an optional extra-resource tracker per
resource (e.g. Sorcery Points), and the spell list with add/edit
dialogs. POINTS and DARK pools get a +/- spend control; DARK also shows
its Vigor-derived River capacity and Vigor Regeneration (VR).

Each spell row toggles an extended view (label:value block + markdown
description, PHB-independent) on a whole-row click; the trailing
edit/delete buttons sit outside the clickable area so they don't toggle.
"""

from nicegui import ui

from app.schemas.char_sheet_global import MagicType
from app.schemas.char_sheet_specific import (
    CharacterSpell,
    DarkParams,
    ExtraResource,
    MagicResource,
)
from app.ui.components.sheet.helpers import (
    _fmt_bonus,
    _render_slot_checkboxes,
    render_detail_pairs,
    render_pm_adjuster,
    render_plain_markdown,
    toggle_element_display,
)
from app.ui.theme import DIALOG_CARD_STYLE, notify_error


def _dark_fields(inp_type, *, vessel=0, current=0, vessel_misc=0,
                 river_misc=0, vr_base=0, vr_misc=0):
    """Render the DARK-only inputs (shown only when the type select is 'Dark').

    Returns the six input handles in a stable order:
    (vessel, current, vessel_misc, river_misc, vr_base, vr_misc).
    """
    container = ui.column().classes('w-full gap-1')
    container.bind_visibility_from(inp_type, 'value', value=MagicType.DARK.value)
    with container:
        with ui.row().classes('w-full gap-2'):
            d_vessel = ui.number("Vessel (base)", value=vessel, min=0, step=1).classes('flex-1').props('dense')
            d_current = ui.number("Current Dark", value=current, min=0, step=1).classes('flex-1').props('dense')
        with ui.row().classes('w-full gap-2'):
            d_vessel_misc = ui.number("Vessel misc", value=vessel_misc, step=1).classes('flex-1').props('dense')
            d_river_misc = ui.number("River misc", value=river_misc, step=1).classes('flex-1').props('dense')
        with ui.row().classes('w-full gap-2'):
            d_vr_base = ui.number("VR base", value=vr_base, step=1).classes('flex-1').props('dense')
            d_vr_misc = ui.number("VR misc", value=vr_misc, step=1).classes('flex-1').props('dense')
        ui.label("Dark spends on the sheet. River capacity = Vigor mod + River misc.").classes('text-xs text-gray-500')
    return d_vessel, d_current, d_vessel_misc, d_river_misc, d_vr_base, d_vr_misc


def _dark_params_from(d_vessel_misc, d_vr_base, d_vr_misc, d_river_misc) -> DarkParams:
    return DarkParams(
        vessel_misc=int(d_vessel_misc.value or 0),
        vr_base=int(d_vr_base.value or 0),
        vr_misc=int(d_vr_misc.value or 0),
        river_misc=int(d_river_misc.value or 0),
    )


def _render_magic_tab(state, cs, magic, _save):
    resources = magic.get("resources", [])
    spells = magic.get("spells", [])

    # DARK casters have no "prepared" concept — spells are always prepared and the
    # meaningful flag is river membership (reusing `prepared`). Relabel accordingly.
    has_dark = any(r['magic_type'] == MagicType.DARK.value for r in resources)
    prepared_label = "River" if has_dark else "Prepared"

    # Which resource expansions are open. Bound into page `state` so they survive
    # the `_save` re-render — otherwise spending a pool with +/- collapses the card
    # on every click.
    expanded = state.setdefault("magic_expanded", set())

    if not resources:
        ui.label("No magic resources yet. Add one to start tracking spells.").classes('text-gray-500 italic text-sm py-2')

    for r in resources:
        exp = ui.expansion(f"{r['name']} ({r['magic_type']})", icon='auto_awesome',
                           value=(r['name'] in expanded)).classes('w-full border border-gray-700 rounded mb-1')
        exp.on_value_change(lambda e, n=r['name']: expanded.add(n) if e.value else expanded.discard(n))
        with exp:
            with ui.row().classes('gap-6 text-sm'):
                ui.label(f"Attribute: {r['attribute'] or '—'}").classes('text-gray-400')
                ui.label(f"Attack: {_fmt_bonus(r['spell_attack_total'])}").classes('text-white')
                ui.label(f"Save DC: {r['spell_dc_total']}").classes('text-white')

            rname = r['name']
            cur_list = r['current']
            max_list = r['maximum']
            mtype = r['magic_type']

            if isinstance(cur_list, list) and isinstance(max_list, list):
                # Spend/recover a single-pool resource (POINTS or DARK): clamp
                # current[0] to [0, cap] and persist.
                def _pool_adjuster(n, cap):
                    async def _adj(delta):
                        updated = []
                        for mr in cs.magic_resources:
                            d = mr.model_dump()
                            if mr.name == n and isinstance(d.get("current"), list) and d["current"]:
                                d["current"][0] = max(0, min(cap, d["current"][0] + delta))
                            updated.append(d)
                        await _save({"magic_resources": updated})
                    return _adj

                if mtype == MagicType.DARK.value:
                    dk = r.get('dark') or {}
                    vessel_total = dk.get('vessel_total', max_list[0] if max_list else 0)
                    with ui.row().classes('items-center gap-2 mt-1'):
                        ui.label(f"Dark: {cur_list[0] if cur_list else 0} / {vessel_total}").classes('text-gray-300 text-sm')
                        render_pm_adjuster(_pool_adjuster(rname, vessel_total))
                    with ui.row().classes('gap-4 mt-1'):
                        ui.label(f"River: {dk.get('river_total', 0)} spells").classes('text-gray-400 text-xs')
                        ui.label(f"VR: {dk.get('vr_total', 0)}").classes('text-gray-400 text-xs')
                elif mtype == MagicType.POINTS.value:
                    with ui.row().classes('items-center gap-2 mt-1'):
                        ui.label(f"Points: {cur_list[0] if cur_list else 0} / {max_list[0] if max_list else 0}").classes('text-gray-300 text-sm')
                        render_pm_adjuster(_pool_adjuster(rname, max_list[0] if max_list else 0))
                else:
                    _render_slot_checkboxes(cs, rname, cur_list, max_list, mtype, _save)

                # Reset restores the pool to full — for DARK that's vessel_total
                # (base + misc), otherwise the stored maximum.
                _dark_cap = (r.get('dark') or {}).get('vessel_total') if mtype == MagicType.DARK.value else None

                async def _reset_resource(n=rname, dark_cap=_dark_cap):
                    updated = []
                    for mr in cs.magic_resources:
                        d = mr.model_dump()
                        if mr.name == n and isinstance(d.get("maximum"), list):
                            d["current"] = [dark_cap] if dark_cap is not None else list(d["maximum"])
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

        # Filter selections survive _save re-renders by living on `state`.
        # Local @ui.refreshable lets a checkbox toggle re-render the list
        # immediately without threading a refresh handle through the
        # features.py dispatcher.
        filt = state.setdefault("spell_filters", {"prepared": False, "concentration": False, "ritual": False})

        @ui.refreshable
        def _spells_section():
            with ui.row().classes('items-center gap-3 mb-1'):
                ui.label("Filter:").classes('text-xs text-gray-500')
                for key, label in ((("prepared", prepared_label),
                                    ("concentration", "Concentration"),
                                    ("ritual", "Ritual"))):
                    def _on_change(e, k=key):
                        filt[k] = bool(e.value)
                        _spells_section.refresh()
                    ui.checkbox(label, value=filt[key], on_change=_on_change).props('dense')

            if not spells:
                ui.label("No spells added yet.").classes('text-gray-500 italic text-sm py-1')
            else:
                visible_spells = [
                    s for s in spells
                    if (not filt["prepared"]      or s.get("prepared"))
                    and (not filt["concentration"] or s.get("concentration"))
                    and (not filt["ritual"]        or s.get("ritual"))
                ]
                if not visible_spells:
                    ui.label("No spells match the active filters.").classes('text-gray-500 italic text-sm py-1')
                else:
                    sorted_spells = sorted(visible_spells, key=lambda s: (s['level'], s['name']))
                    for sp_idx, sp in enumerate(sorted_spells):
                        orig_idx = spells.index(sp)
                        sp_name = sp['name']
                        with ui.column().classes('w-full gap-0'):
                            with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                                # Whole info area toggles the extended view; the
                                # edit/delete buttons sit outside it so their
                                # clicks never reach the toggle.
                                info_row = ui.row().classes('flex-1 items-center gap-2 cursor-pointer no-wrap')
                                with info_row:
                                    level_lbl = "C" if sp['level'] == 0 else str(sp['level'])
                                    ui.label(level_lbl).classes('w-6 text-center text-xs text-gray-400')
                                    name_classes = 'text-sm flex-1'
                                    name_classes += ' text-white font-bold' if sp.get('prepared') else ' text-gray-300'
                                    ui.label(sp_name).classes(name_classes)
                                    if sp.get('ritual'):
                                        ui.badge('R', color='purple').props('dense')
                                    ui.label(sp.get('casting_time') or '—').classes('w-20 text-gray-400 text-xs')
                                    ui.label(sp.get('spell_range') or '—').classes('w-16 text-gray-400 text-xs')
                                    dur = sp.get('duration') or ''
                                    dur_display = f"Conc. {dur}" if sp.get('concentration') and dur else ('Conc.' if sp.get('concentration') else dur or '—')
                                    ui.label(dur_display).classes('w-24 text-gray-400 text-xs')
                                    ui.label(sp.get('resource_name') or '—').classes('w-24 text-gray-400 text-sm')
                                ui.button(icon='edit', on_click=lambda n=sp_name, i=orig_idx: _open_edit_spell(cs, _save, resources, n, i)).props('flat round dense color=primary')
                                async def _rm_spell(n=sp_name):
                                    updated = [s for s in cs.spells if s.name != n]
                                    await _save({"spells": [s.model_dump() for s in updated]})
                                ui.button(icon='delete', on_click=_rm_spell).props('flat round dense color=negative')
                            desc_row = ui.column().classes('w-full pl-8 py-1 gap-1 border-b border-gray-800').style('display: none')
                            with desc_row:
                                render_detail_pairs([
                                    ("Level", "Cantrip" if sp['level'] == 0 else str(sp['level'])),
                                    ("School", sp.get('school')),
                                    ("Casting Time", sp.get('casting_time')),
                                    ("Range", sp.get('spell_range')),
                                    ("Duration", sp.get('duration')),
                                    ("Concentration", "Yes" if sp.get('concentration') else "No"),
                                    ("Ritual", "Yes" if sp.get('ritual') else "No"),
                                    ("Resource", sp.get('resource_name')),
                                    (prepared_label, "Yes" if sp.get('prepared') else "No"),
                                ])
                                render_plain_markdown(sp.get('description'))
                            info_row.on('click', lambda dr=desc_row: toggle_element_display(dr))

            ui.button("Add Spell", icon='add', on_click=lambda: _open_add_spell(cs, _save, resources)).props('unelevated color=indigo').classes('mt-2')

        _spells_section()


def _open_add_resource(cs, _save, resources):
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Add Magic Resource").classes('text-lg font-bold mb-2 text-white')
        inp_name = ui.input("Name", value="Spellcasting").classes('w-full')
        inp_src  = ui.input("Source (class/feat/item)").classes('w-full')
        inp_type = ui.select([t.value for t in MagicType], label="Magic Type", value=MagicType.PERLEVEL.value).classes('w-full')
        inp_attr = ui.select(["STR","DEX","CON","INT","WIS","CHA"] + (["VIG"] if cs.vigor_enabled else []) + [None], label="Attribute", value="INT").classes('w-full')
        with ui.row().classes('w-full gap-2'):
            inp_atk_misc = ui.number("Attack Misc", value=0, step=1).classes('flex-1').props('dense')
            inp_dc_misc  = ui.number("DC Misc",    value=0, step=1).classes('flex-1').props('dense')
        slots_container = ui.column().classes('w-full gap-0')
        slots_container.bind_visibility_from(inp_type, 'value', backward=lambda v: v != MagicType.DARK.value)
        with slots_container:
            inp_slots = ui.input("Slots (comma-separated, e.g. 4,2)", value="").classes('w-full')
            ui.label("SLOTS: one entry. PERLEVEL: per level. SHADOWDARK/POINTS: leave blank or single.").classes('text-xs text-gray-500')

        d_vessel, d_current, d_vessel_misc, d_river_misc, d_vr_base, d_vr_misc = _dark_fields(inp_type)

        # DARK casters are Vigor-powered: default the attribute to VIG when picked.
        def _default_dark_attr():
            if inp_type.value == MagicType.DARK.value and cs.vigor_enabled:
                inp_attr.value = "VIG"
        inp_type.on_value_change(_default_dark_attr)

        # extra_resource is a general secondary pool (e.g. Sorcery Points); it is
        # redundant for DARK (which has its own vessel/river/VR), so hide it there.
        er_wrap = ui.column().classes('w-full gap-0')
        er_wrap.bind_visibility_from(inp_type, 'value', backward=lambda v: v != MagicType.DARK.value)
        with er_wrap:
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
                if mt == MagicType.DARK:
                    cur_val = [int(d_current.value or 0)]
                    max_val = [int(d_vessel.value or 0)]
                    dark = _dark_params_from(d_vessel_misc, d_vr_base, d_vr_misc, d_river_misc)
                else:
                    cur_val, max_val, dark = slots, slots, None
                entry = MagicResource(
                    name=name,
                    source=(inp_src.value or "").strip(),
                    magic_type=mt,
                    attribute=inp_attr.value,
                    spell_attack_misc=int(inp_atk_misc.value or 0),
                    spell_dc_misc=int(inp_dc_misc.value or 0),
                    current=cur_val,
                    maximum=max_val,
                    extra_resource=extra,
                    dark=dark,
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
    _dk = res_obj.dark
    _dark_seed = dict(
        vessel=(old_max[0] if isinstance(old_max, list) and old_max else 0),
        current=(res_obj.current[0] if isinstance(res_obj.current, list) and res_obj.current else 0),
        vessel_misc=(_dk.vessel_misc if _dk else 0),
        river_misc=(_dk.river_misc if _dk else 0),
        vr_base=(_dk.vr_base if _dk else 0),
        vr_misc=(_dk.vr_misc if _dk else 0),
    )

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Edit Magic Resource").classes('text-lg font-bold mb-2 text-white')
        inp_name = ui.input("Name", value=res_obj.name).classes('w-full')
        inp_src  = ui.input("Source (class/feat/item)", value=res_obj.source or "").classes('w-full')
        inp_type = ui.select([t.value for t in MagicType], label="Magic Type", value=res_obj.magic_type.value if hasattr(res_obj.magic_type, 'value') else res_obj.magic_type).classes('w-full')
        inp_attr = ui.select(["STR","DEX","CON","INT","WIS","CHA"] + (["VIG"] if cs.vigor_enabled else []) + [None], label="Attribute", value=res_obj.attribute).classes('w-full')
        with ui.row().classes('w-full gap-2'):
            inp_atk_misc = ui.number("Attack Misc", value=res_obj.spell_attack_misc, step=1).classes('flex-1').props('dense')
            inp_dc_misc  = ui.number("DC Misc", value=res_obj.spell_dc_misc, step=1).classes('flex-1').props('dense')
        slots_container = ui.column().classes('w-full gap-0')
        slots_container.bind_visibility_from(inp_type, 'value', backward=lambda v: v != MagicType.DARK.value)
        with slots_container:
            inp_slots = ui.input("Slots (comma-separated, e.g. 4,2)", value=old_slots_str).classes('w-full')
            ui.label("SLOTS: one entry. PERLEVEL: per level. SHADOWDARK/POINTS: leave blank or single.").classes('text-xs text-gray-500')

        d_vessel, d_current, d_vessel_misc, d_river_misc, d_vr_base, d_vr_misc = _dark_fields(inp_type, **_dark_seed)

        def _default_dark_attr():
            if inp_type.value == MagicType.DARK.value and cs.vigor_enabled:
                inp_attr.value = "VIG"
        inp_type.on_value_change(_default_dark_attr)

        # extra_resource is redundant for DARK (its vessel/river/VR cover it) — hide there.
        er_wrap = ui.column().classes('w-full gap-0')
        er_wrap.bind_visibility_from(inp_type, 'value', backward=lambda v: v != MagicType.DARK.value)
        with er_wrap:
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
                if mt == MagicType.DARK:
                    cur_val = [int(d_current.value or 0)]
                    max_val = [int(d_vessel.value or 0)]
                    dark = _dark_params_from(d_vessel_misc, d_vr_base, d_vr_misc, d_river_misc)
                else:
                    cur_val = new_slots if new_slots != old_max else res_obj.current
                    max_val = new_slots
                    dark = None
                entry = MagicResource(
                    name=name,
                    source=(inp_src.value or "").strip(),
                    magic_type=mt,
                    attribute=inp_attr.value,
                    spell_attack_misc=int(inp_atk_misc.value or 0),
                    spell_dc_misc=int(inp_dc_misc.value or 0),
                    current=cur_val,
                    maximum=max_val,
                    extra_resource=extra,
                    dark=dark,
                )
                updated = [mr.model_dump() for mr in cs.magic_resources]
                updated[idx] = entry.model_dump()
                updates = {"magic_resources": updated}
                old_name = res_obj.name
                if name != old_name:
                    updated_spells = []
                    for sp in cs.spells:
                        d = sp.model_dump()
                        if d.get("resource_name") == old_name:
                            d["resource_name"] = name
                        updated_spells.append(d)
                    updates["spells"] = updated_spells
                await _save(updates)
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
        _prep_label = "River" if any(r.get('magic_type') == MagicType.DARK.value for r in resources) else "Prepared"
        inp_prep   = ui.checkbox(_prep_label)

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
        options = list(resource_names)
        if spell_obj.resource_name and spell_obj.resource_name not in options:
            options.append(spell_obj.resource_name)
        options.append(None)
        inp_res    = ui.select(options, label="Resource", value=spell_obj.resource_name).classes('w-full')
        _prep_label = "River" if any(r.get('magic_type') == MagicType.DARK.value for r in resources) else "Prepared"
        inp_prep   = ui.checkbox(_prep_label, value=spell_obj.prepared)

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
