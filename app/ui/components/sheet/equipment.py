"""Equipment card — currency plus the weapons / armor / items inventory tabs.

Reads `state["cs"].inventory` directly (not the builder view-model) and splits
it by `item_type`. Each item row's name toggles an extended view (fields not on
the display line + a markdown description stored in `InventoryItem.notes`,
rendered PHB-independent). Add/edit/custom dialogs expose the description as a
markdown textarea; every write goes through the page `_save`.
"""

from nicegui import ui

from app.ui.theme import DIALOG_CARD_STYLE, notify_error, notify_success
from app.schemas.char_sheet_specific import InventoryItem
from app.schemas.char_sheet_global import CustomWeaponInput, CustomArmorInput, CustomItemInput
from app.services.session import service_session
from app.services.global_items_service import (
    list_weapons, list_armor, list_items,
    add_custom_weapon, add_custom_armor, add_custom_item,
)
from app.ui.components.sheet.helpers import (
    render_detail_pairs,
    render_plain_markdown,
    render_pm_adjuster,
    toggle_element_display,
)


def _render_equipment(state, char_id, user, _save):

    @ui.refreshable
    def _section():
        cs = state["cs"]
        inventory = cs.inventory

        weapons = [i for i in inventory if i.item_type == "weapon"]
        armors  = [i for i in inventory if i.item_type == "armor"]
        items   = [i for i in inventory if i.item_type == "item"]

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Equipment").classes('text-xl font-bold font-serif')

            ui.separator()

            with ui.tabs().classes('w-full').bind_value(state, "equipment_tab") as tabs:
                # Keep the internal tab name "Coins" (the value bound into
                # state["equipment_tab"]) stable; only the display label changes
                # to "Currency" so it reads correctly for gp / $ / credits.
                tab_c = ui.tab("Coins", label="Currency")
                tab_w = ui.tab("Weapons")
                tab_a = ui.tab("Armor")
                tab_i = ui.tab("Items")

            with ui.tab_panels(tabs, value=state["equipment_tab"]).classes('w-full').bind_value(state, "equipment_tab").style('max-height: 400px; overflow-y: auto;'):

                # --- Currency tab ---
                with ui.tab_panel(tab_c):
                    money = dict(cs.currency or {})

                    async def _set_money(key: str, value: int):
                        new_money = dict(cs.currency or {})
                        new_money[key] = max(0, int(value or 0))
                        await _save({"currency": new_money})

                    async def _bump_money(key: str, delta: int):
                        new_money = dict(cs.currency or {})
                        new_money[key] = max(0, int(new_money.get(key, 0)) + delta)
                        await _save({"currency": new_money})

                    async def _remove_currency(key: str):
                        new_money = dict(cs.currency or {})
                        new_money.pop(key, None)
                        await _save({"currency": new_money})

                    if not money:
                        ui.label("No currency tracked.").classes('text-gray-500 italic text-sm py-1')
                    else:
                        with ui.row().classes('w-full items-center gap-3 flex-wrap'):
                            for key in list(money.keys()):
                                with ui.column().classes('items-center gap-0 border border-gray-700 rounded p-2 min-w-[110px]'):
                                    ui.label(key).classes('text-xs text-gray-400 font-bold')
                                    with ui.row().classes('items-center gap-1'):
                                        ui.button(icon='remove',
                                                  on_click=lambda _, k=key: _bump_money(k, -1)
                                                  ).props('flat round dense size=sm color=negative')
                                        amt_input = ui.number(value=money[key], min=0, step=1).props('dense outlined').classes('w-20')
                                        amt_input.on_value_change(lambda e, k=key: _set_money(k, e.value))
                                        ui.button(icon='add',
                                                  on_click=lambda _, k=key: _bump_money(k, 1)
                                                  ).props('flat round dense size=sm color=positive')
                                    ui.button(icon='delete',
                                              on_click=lambda _, k=key: _remove_currency(k)
                                              ).props('flat round dense size=sm color=grey')

                    def _open_add_currency():
                        with ui.dialog() as dlg, ui.card().classes('w-80').style(DIALOG_CARD_STYLE):
                            ui.label("Add Currency").classes('text-lg font-bold text-white mb-2')
                            name_in = ui.input(label="Currency code (e.g. SP, GP)").props('dense outlined').classes('w-full')
                            amt_in = ui.number(label="Starting amount", value=0, min=0, step=1).props('dense outlined').classes('w-full')
                            with ui.row().classes('w-full justify-end gap-2 mt-2'):
                                ui.button("Cancel", on_click=dlg.close).props('flat').style('color:#94A3B8;')

                                async def _add():
                                    code = (name_in.value or "").strip()
                                    if not code:
                                        return
                                    new_money = dict(cs.currency or {})
                                    new_money[code] = int(amt_in.value or 0)
                                    await _save({"currency": new_money})
                                    dlg.close()

                                ui.button("Add", on_click=_add).props('unelevated color=primary')
                        dlg.open()

                    ui.button("Add Currency", icon='add', on_click=_open_add_currency
                              ).props('flat dense').classes('text-indigo-400 mt-2')

                # --- Weapons tab ---
                with ui.tab_panel(tab_w):
                    if not weapons:
                        ui.label("No weapons carried.").classes('text-gray-500 italic text-sm py-1')
                    else:
                        with ui.row().classes('w-full text-xs text-gray-500 px-1 mb-1 gap-2'):
                            for h in ["Eq", "Name", "Damage", "Type", "Range", "Properties", "Qty", ""]:
                                if h == "Eq":
                                    ui.label(h).classes('w-8 text-center')
                                elif h in ("Qty", ""):
                                    ui.label(h).classes('w-10 text-center')
                                else:
                                    ui.label(h).classes('flex-1')

                        for w in weapons:
                            with ui.column().classes('w-full gap-0'):
                                with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                                    wname = w.name
                                    async def _toggle_w(v, n=wname):
                                        updated = []
                                        for it in cs.inventory:
                                            if it.item_type == "weapon" and it.name == n:
                                                d = it.model_dump()
                                                d["equipped"] = bool(v)
                                                updated.append(d)
                                            else:
                                                updated.append(it.model_dump())
                                        await _save({"inventory": updated})
                                    ui.checkbox(value=bool(w.equipped),
                                                on_change=lambda e, n=wname: _toggle_w(e.value, n)
                                                ).classes('w-8')
                                    # Name toggles the extended view (the equip
                                    # checkbox and edit/delete stay independent).
                                    name_lbl = ui.label(w.name).classes('flex-1 text-white text-sm cursor-pointer')
                                    ui.label(w.damage or "—").classes('flex-1 text-gray-300 text-sm')
                                    ui.label(w.damage_type or "—").classes('flex-1 text-gray-400 text-sm')
                                    ui.label(w.weapon_range or "—").classes('flex-1 text-gray-400 text-sm')
                                    ui.label(w.item_notes or "—").classes('flex-1 text-gray-400 text-xs')
                                    ui.label(str(w.quantity)).classes('w-10 text-center text-white text-sm')
                                    ui.button(icon='edit',
                                              on_click=lambda n=wname: _open_edit_inventory_dialog(cs, _save, _section, n, "weapon")
                                              ).props('flat round dense color=primary')
                                    async def _rm_w(n=wname):
                                        updated = [it for it in cs.inventory if it.name != n or it.item_type != "weapon"]
                                        await _save({"inventory": [it.model_dump() for it in updated]})
                                    ui.button(icon='delete', on_click=_rm_w).props('flat round dense color=negative')
                                desc_row = ui.column().classes('w-full pl-8 py-1 gap-1 border-b border-gray-800').style('display: none')
                                with desc_row:
                                    render_detail_pairs([
                                        ("Weight", w.weight),
                                        ("Value", w.value),
                                        ("Attuned", "Yes" if w.attuned else "No"),
                                    ])
                                    render_plain_markdown(w.notes)
                                name_lbl.on('click', lambda dr=desc_row: toggle_element_display(dr))

                    with ui.row().classes('gap-2 mt-2'):
                        async def _add_w_from_db():
                            await _open_picker_dialog(cs, state, user, _save, _section, "weapon")
                        def _add_w_custom():
                            _open_custom_dialog(cs, state, user, _save, _section, "weapon")
                        ui.button("Add from Library", icon='library_add', on_click=_add_w_from_db).props('flat dense').classes('text-indigo-400')
                        ui.button("Add Custom", icon='add', on_click=_add_w_custom).props('flat dense').classes('text-gray-400')

                # --- Armor tab ---
                with ui.tab_panel(tab_a):
                    if not armors:
                        ui.label("No armor carried.").classes('text-gray-500 italic text-sm py-1')
                    else:
                        with ui.row().classes('w-full text-xs text-gray-500 px-1 mb-1 gap-2'):
                            for h in ["Eq", "Name", "AC", "Base", "Dex Cap", "Shield?", "Weight", "Qty", ""]:
                                if h == "Eq":
                                    ui.label(h).classes('w-8 text-center')
                                elif h in ("Qty", ""):
                                    ui.label(h).classes('w-10 text-center')
                                else:
                                    ui.label(h).classes('flex-1')
                        for a in armors:
                            with ui.column().classes('w-full gap-0'):
                                with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                                    aname = a.name
                                    aname_is_shield = bool(a.is_shield)

                                    async def _toggle_a(v, n=aname, shield=aname_is_shield):
                                        updated = []
                                        for it in cs.inventory:
                                            d = it.model_dump()
                                            if it.item_type == "armor":
                                                same_kind = bool(it.is_shield) == shield
                                                if it.name == n:
                                                    d["equipped"] = bool(v)
                                                elif v and same_kind:
                                                    d["equipped"] = False
                                            updated.append(d)
                                        await _save({"inventory": updated})

                                    ui.checkbox(value=bool(a.equipped),
                                                on_change=lambda e, n=aname, s=aname_is_shield: _toggle_a(e.value, n, s)
                                                ).classes('w-8')
                                    name_lbl = ui.label(a.name).classes('flex-1 text-white text-sm cursor-pointer')
                                    ui.label(a.armor_class or "—").classes('flex-1 text-gray-300 text-sm')
                                    ui.label(str(a.base_ac) if a.base_ac is not None else "—").classes('flex-1 text-gray-400 text-sm')
                                    ui.label("∞" if a.dex_cap is None else str(a.dex_cap)).classes('flex-1 text-gray-400 text-sm')
                                    ui.label("Yes" if a.is_shield else "No").classes('flex-1 text-gray-400 text-sm')
                                    ui.label(a.weight or "—").classes('flex-1 text-gray-400 text-sm')
                                    ui.label(str(a.quantity)).classes('w-10 text-center text-white text-sm')
                                    ui.button(icon='edit',
                                              on_click=lambda n=aname: _open_edit_inventory_dialog(cs, _save, _section, n, "armor")
                                              ).props('flat round dense color=primary')
                                    async def _rm_a(n=aname):
                                        updated = [it for it in cs.inventory if it.name != n or it.item_type != "armor"]
                                        await _save({"inventory": [it.model_dump() for it in updated]})
                                    ui.button(icon='delete', on_click=_rm_a).props('flat round dense color=negative')
                                desc_row = ui.column().classes('w-full pl-8 py-1 gap-1 border-b border-gray-800').style('display: none')
                                with desc_row:
                                    render_detail_pairs([
                                        ("Value", a.value),
                                        ("Properties", a.item_notes),
                                        ("Attuned", "Yes" if a.attuned else "No"),
                                    ])
                                    render_plain_markdown(a.notes)
                                name_lbl.on('click', lambda dr=desc_row: toggle_element_display(dr))

                    with ui.row().classes('gap-2 mt-2'):
                        ui.button("Add from Library", icon='library_add',
                                  on_click=lambda: _open_picker_dialog(cs, state, user, _save, _section, "armor")
                                  ).props('flat dense').classes('text-indigo-400')
                        ui.button("Add Custom", icon='add',
                                  on_click=lambda: _open_custom_dialog(cs, state, user, _save, _section, "armor")
                                  ).props('flat dense').classes('text-gray-400')

                # --- Items tab ---
                with ui.tab_panel(tab_i):
                    if not items:
                        ui.label("No equipment carried.").classes('text-gray-500 italic text-sm py-1')
                    else:
                        with ui.row().classes('w-full text-xs text-gray-500 px-1 mb-1 gap-2'):
                            for h in ["Name", "Weight", "Value", "Qty", ""]:
                                if h == "Qty":
                                    ui.label(h).classes('w-24 text-center')
                                elif h == "":
                                    ui.label(h).classes('w-10 text-center')
                                else:
                                    ui.label(h).classes('flex-1')
                        for it in items:
                            with ui.column().classes('w-full gap-0'):
                                with ui.row().classes('w-full items-center border-b border-gray-800 py-1 gap-2'):
                                    iname = it.name
                                    name_lbl = ui.label(it.name).classes('flex-1 text-white text-sm cursor-pointer')
                                    ui.label(it.weight or "—").classes('flex-1 text-gray-400 text-sm')
                                    ui.label(it.value or "—").classes('flex-1 text-gray-400 text-sm')

                                    async def _qty_adjust(delta: int, n=iname):
                                        updated = []
                                        for x in cs.inventory:
                                            d = x.model_dump()
                                            if x.name == n and x.item_type == "item":
                                                d["quantity"] = max(0, d["quantity"] + delta)
                                            updated.append(d)
                                        await _save({"inventory": updated})

                                    with ui.row().classes('w-24 items-center justify-center gap-1 no-wrap'):
                                        ui.label(str(it.quantity)).classes('text-white text-sm')
                                        render_pm_adjuster(_qty_adjust)
                                    ui.button(icon='edit',
                                              on_click=lambda n=iname: _open_edit_inventory_dialog(cs, _save, _section, n, "item")
                                              ).props('flat round dense color=primary')
                                    async def _rm_i(n=iname):
                                        updated = [x for x in cs.inventory if x.name != n or x.item_type != "item"]
                                        await _save({"inventory": [x.model_dump() for x in updated]})
                                    ui.button(icon='delete', on_click=_rm_i).props('flat round dense color=negative')
                                desc_row = ui.column().classes('w-full pl-8 py-1 gap-1 border-b border-gray-800').style('display: none')
                                with desc_row:
                                    render_detail_pairs([
                                        ("Properties", it.item_notes),
                                        ("Equipped", "Yes" if it.equipped else "No"),
                                        ("Attuned", "Yes" if it.attuned else "No"),
                                    ])
                                    render_plain_markdown(it.notes)
                                name_lbl.on('click', lambda dr=desc_row: toggle_element_display(dr))

                    with ui.row().classes('gap-2 mt-2'):
                        ui.button("Add from Library", icon='library_add',
                                  on_click=lambda: _open_picker_dialog(cs, state, user, _save, _section, "item")
                                  ).props('flat dense').classes('text-indigo-400')
                        ui.button("Add Custom", icon='add',
                                  on_click=lambda: _open_custom_dialog(cs, state, user, _save, _section, "item")
                                  ).props('flat dense').classes('text-gray-400')

    _section()
    return _section


async def _open_picker_dialog(cs, state, user, _save, refresh_fn, item_type: str):
    # Invoked from a button-click handler: the client is already connected and a
    # slot context is active, so load the library rows and build the dialog
    # inline. (Do NOT defer this onto a background task — defer_load runs without
    # a slot context, so dialog construction raises and is silently swallowed.)
    async with service_session() as session:
        style = cs.style
        owner_id = user.id
        if item_type == "weapon":
            rows = await list_weapons(session, style, owner_id)
        elif item_type == "armor":
            rows = await list_armor(session, style, owner_id)
        else:
            rows = await list_items(session, style, owner_id)

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg').style(DIALOG_CARD_STYLE):
        ui.label(f"Add {item_type.title()} from Library").classes('text-lg font-bold mb-2 text-white')

        if not rows:
            ui.label(f"No {item_type}s found. Run `python -m app.cli.ingest data/` to populate.").classes('text-yellow-400 text-sm')
            ui.button("Close", on_click=dialog.close).props('flat')
            dialog.open()
            return

        options = {r.name: r for r in rows}
        selected = ui.select(
            options=list(options.keys()),
            label=f"Choose {item_type}",
            value=list(options.keys())[0],
            with_input=True,
        ).classes('w-full')
        qty_inp = ui.number("Quantity", value=1, step=1, min=1).classes('w-full').props('dense')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm():
                r = options[selected.value]
                if item_type == "weapon":
                    inv_item = InventoryItem(
                        item_type="weapon", name=r.name,
                        quantity=int(qty_inp.value or 1),
                        damage=r.damage, damage_type=r.damage_type,
                        weapon_range=r.range, weight=r.weight, value=r.value,
                        item_notes=r.notes,
                    )
                elif item_type == "armor":
                    inv_item = InventoryItem(
                        item_type="armor", name=r.name,
                        quantity=int(qty_inp.value or 1),
                        armor_class=r.armor_class,
                        base_ac=r.base_ac, dex_cap=r.dex_cap,
                        is_shield=bool(r.is_shield),
                        weight=r.weight, value=r.value,
                        item_notes=r.notes,
                    )
                else:
                    inv_item = InventoryItem(
                        item_type="item", name=r.name,
                        quantity=int(qty_inp.value or 1),
                        weight=r.weight, value=r.value,
                        # Surface the global item's effects (e.g. a UM5 vehicle's
                        # Cap/Speed/AC/HP or a cybernetic's location) as Properties.
                        item_notes=r.effects,
                    )
                updated = [it.model_dump() for it in cs.inventory] + [inv_item.model_dump()]
                await _save({"inventory": updated})
                dialog.close()
                refresh_fn.refresh()

            ui.button("Add", on_click=_confirm).props('unelevated color=primary')

    dialog.open()


def _open_custom_dialog(cs, state, user, _save, refresh_fn, item_type: str):

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label(f"Add Custom {item_type.title()}").classes('text-lg font-bold mb-2 text-white')
        inp_name = ui.input("Name*").classes('w-full')
        qty_inp  = ui.number("Quantity", value=1, step=1, min=1).classes('w-full').props('dense')

        if item_type == "weapon":
            inp_type   = ui.input("Type (e.g. Simple Melee)").classes('w-full').props('dense')
            inp_dmg    = ui.input("Damage (e.g. 1d8)").classes('w-full').props('dense')
            inp_dmgt   = ui.input("Damage Type (e.g. slashing)").classes('w-full').props('dense')
            inp_range  = ui.input("Range (e.g. 20/60)").classes('w-full').props('dense')
            inp_weight = ui.input("Weight").classes('w-full').props('dense')
            inp_value  = ui.input("Cost").classes('w-full').props('dense')
            inp_notes  = ui.input("Properties").classes('w-full').props('dense')
        elif item_type == "armor":
            inp_type   = ui.input("Type (e.g. Light)").classes('w-full').props('dense')
            inp_ac     = ui.input("AC (e.g. 11 + Dex)").classes('w-full').props('dense')
            inp_str    = ui.input("Strength Requirement").classes('w-full').props('dense')
            inp_weight = ui.input("Weight").classes('w-full').props('dense')
            inp_value  = ui.input("Cost").classes('w-full').props('dense')
            inp_notes  = ui.input("Notes").classes('w-full').props('dense')
        else:
            inp_type   = ui.input("Type").classes('w-full').props('dense')
            inp_weight = ui.input("Weight").classes('w-full').props('dense')
            inp_value  = ui.input("Cost").classes('w-full').props('dense')
            inp_effects = ui.input("Effects/Notes").classes('w-full').props('dense')

        # Free-form markdown description, shown in the row's extended view.
        inp_desc = ui.textarea("Description (markdown)").classes('w-full').props('rows=3')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm():
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name is required"); return
                desc = (inp_desc.value or "").strip()

                async with service_session() as session:
                    if item_type == "weapon":
                        dto = CustomWeaponInput(
                            name=name, weapon_type=inp_type.value, damage=inp_dmg.value,
                            damage_type=inp_dmgt.value, weapon_range=inp_range.value,
                            weight=inp_weight.value, value=inp_value.value, notes=inp_notes.value,
                        )
                        await add_custom_weapon(session, user.id, cs.style, dto)
                        inv_item = InventoryItem(
                            item_type="weapon", name=name, quantity=int(qty_inp.value or 1),
                            damage=dto.damage, damage_type=dto.damage_type,
                            weapon_range=dto.weapon_range, weight=dto.weight,
                            value=dto.value, item_notes=dto.notes, notes=desc,
                            is_custom=True,
                        )
                    elif item_type == "armor":
                        from app.cli.ingest import parse_armor_stats
                        base_ac, dex_cap, is_shield = parse_armor_stats(
                            inp_type.value, inp_ac.value, None,
                        )
                        dto = CustomArmorInput(
                            name=name, armor_type=inp_type.value, armor_class=inp_ac.value,
                            strength_requirement=inp_str.value,
                            weight=inp_weight.value, value=inp_value.value, notes=inp_notes.value,
                        )
                        await add_custom_armor(session, user.id, cs.style, dto)
                        inv_item = InventoryItem(
                            item_type="armor", name=name, quantity=int(qty_inp.value or 1),
                            armor_class=dto.armor_class,
                            base_ac=base_ac, dex_cap=dex_cap, is_shield=is_shield,
                            weight=dto.weight,
                            value=dto.value, item_notes=dto.notes, notes=desc,
                            is_custom=True,
                        )
                    else:
                        dto = CustomItemInput(
                            name=name, item_type=inp_type.value,
                            weight=inp_weight.value, value=inp_value.value, effects=inp_effects.value,
                        )
                        await add_custom_item(session, user.id, cs.style, dto)
                        inv_item = InventoryItem(
                            item_type="item", name=name, quantity=int(qty_inp.value or 1),
                            weight=dto.weight, value=dto.value, notes=desc,
                            is_custom=True,
                        )

                updated = [it.model_dump() for it in cs.inventory] + [inv_item.model_dump()]
                await _save({"inventory": updated})
                dialog.close()
                refresh_fn.refresh()
                notify_success(f"Custom {item_type} '{name}' added to library and inventory")

            ui.button("Add", on_click=_confirm).props('unelevated color=primary')

    dialog.open()


def _open_edit_inventory_dialog(cs, _save, refresh_fn, item_name: str, item_type: str):
    """Edit an existing inventory entry's display fields and quantity.

    Edits the inventory snapshot only — never the underlying GlobalWeapon /
    Armor / Item row. Every successful save sets is_custom=True so a
    previously-pristine library snapshot is marked as diverged.
    """
    target = next(
        (x for x in cs.inventory if x.name == item_name and x.item_type == item_type),
        None,
    )
    if not target:
        return
    target_idx = cs.inventory.index(target)

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label(f"Edit {item_type.title()}").classes('text-lg font-bold mb-2 text-white')
        inp_name = ui.input("Name*", value=target.name).classes('w-full')
        qty_inp  = ui.number("Quantity", value=target.quantity, step=1, min=0).classes('w-full').props('dense')

        if item_type == "weapon":
            inp_dmg    = ui.input("Damage (e.g. 1d8)", value=target.damage or "").classes('w-full').props('dense')
            inp_dmgt   = ui.input("Damage Type (e.g. slashing)", value=target.damage_type or "").classes('w-full').props('dense')
            inp_range  = ui.input("Range (e.g. 20/60)", value=target.weapon_range or "").classes('w-full').props('dense')
            inp_weight = ui.input("Weight", value=target.weight or "").classes('w-full').props('dense')
            inp_value  = ui.input("Cost", value=target.value or "").classes('w-full').props('dense')
            inp_notes  = ui.input("Properties", value=target.item_notes or "").classes('w-full').props('dense')
        elif item_type == "armor":
            inp_atype  = ui.input("Type (e.g. Light, Medium, Heavy, Shield)",
                                  value=("Shield" if target.is_shield else "")
                                  ).classes('w-full').props('dense')
            inp_ac     = ui.input("AC (e.g. 11 + Dex)", value=target.armor_class or "").classes('w-full').props('dense')
            inp_weight = ui.input("Weight", value=target.weight or "").classes('w-full').props('dense')
            inp_value  = ui.input("Cost", value=target.value or "").classes('w-full').props('dense')
            inp_notes  = ui.input("Notes", value=target.item_notes or "").classes('w-full').props('dense')
        else:
            inp_weight = ui.input("Weight", value=target.weight or "").classes('w-full').props('dense')
            inp_value  = ui.input("Cost", value=target.value or "").classes('w-full').props('dense')
            inp_notes  = ui.input("Effects/Notes", value=target.item_notes or "").classes('w-full').props('dense')

        # Free-form markdown description, shown in the row's extended view.
        inp_desc = ui.textarea("Description (markdown)", value=target.notes or "").classes('w-full').props('rows=3')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm(idx=target_idx):
                new_name = (inp_name.value or "").strip()
                if not new_name:
                    notify_error("Name is required"); return
                new_qty = max(0, int(qty_inp.value or 0))
                new_desc = (inp_desc.value or "").strip()

                if item_type == "weapon":
                    new_entry = InventoryItem(
                        item_type="weapon",
                        name=new_name,
                        quantity=new_qty,
                        equipped=target.equipped,
                        attuned=target.attuned,
                        notes=new_desc,
                        damage=(inp_dmg.value or "").strip() or None,
                        damage_type=(inp_dmgt.value or "").strip() or None,
                        weapon_range=(inp_range.value or "").strip() or None,
                        weight=(inp_weight.value or "").strip() or None,
                        value=(inp_value.value or "").strip() or None,
                        item_notes=(inp_notes.value or "").strip() or None,
                        is_custom=True,
                    )
                elif item_type == "armor":
                    # Re-derive the numeric AC breakdown from the freeform inputs so
                    # AC math stays consistent — same path the Add-Custom dialog uses.
                    from app.cli.ingest import parse_armor_stats
                    base_ac, dex_cap, is_shield = parse_armor_stats(
                        inp_atype.value or "", inp_ac.value or "", None,
                    )
                    new_entry = InventoryItem(
                        item_type="armor",
                        name=new_name,
                        quantity=new_qty,
                        equipped=target.equipped,
                        attuned=target.attuned,
                        notes=new_desc,
                        armor_class=(inp_ac.value or "").strip() or None,
                        base_ac=base_ac,
                        dex_cap=dex_cap,
                        is_shield=is_shield,
                        weight=(inp_weight.value or "").strip() or None,
                        value=(inp_value.value or "").strip() or None,
                        item_notes=(inp_notes.value or "").strip() or None,
                        is_custom=True,
                    )
                else:
                    new_entry = InventoryItem(
                        item_type="item",
                        name=new_name,
                        quantity=new_qty,
                        equipped=target.equipped,
                        attuned=target.attuned,
                        notes=new_desc,
                        weight=(inp_weight.value or "").strip() or None,
                        value=(inp_value.value or "").strip() or None,
                        item_notes=(inp_notes.value or "").strip() or None,
                        is_custom=True,
                    )

                updated = [x.model_dump() for x in cs.inventory]
                updated[idx] = new_entry.model_dump()
                await _save({"inventory": updated})
                dialog.close()
                refresh_fn.refresh()

            ui.button("Save", on_click=_confirm).props('unelevated color=primary')

    dialog.open()
