from nicegui import ui

from app.ui.async_helpers import defer_load
from app.ui.components.sheet.helpers import make_toggle_handler
from app.schemas.char_sheet_global import SheetStyle
from app.services.session import service_session
from app.services.global_items_service import list_destinies


def _render_description(state, char_id, user, _save):
    @ui.refreshable
    def _section():
        vd = state["vd"]
        cs = state["cs"]
        details = vd.get("details", {})
        is_editing = [False]

        with ui.card().classes('w-full flex-1 min-w-[260px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Description").classes('text-xl font-bold font-serif')
                edit_btn = ui.button(icon='edit').props('flat round dense')
            ui.separator()

            display_col = ui.column().classes('w-full').style('max-height: 600px; overflow-y: auto;')
            edit_col = ui.column().classes('w-full').style('max-height: 600px; overflow-y: auto;')

            hide_ideals = bool(details.get("ideals_suppressed"))
            hide_bonds = bool(details.get("bonds_suppressed"))
            hide_flaws = bool(details.get("flaws_suppressed"))
            hide_alignment = bool(details.get("alignment_suppressed"))

            with display_col:
                rows = [
                    ("Background", cs.background),
                    ("Size", cs.size),
                    ("XP", str(cs.experience_points or "Milestone")),
                ]
                destiny = details.get("destiny")
                if destiny is not None:
                    rows.append(("Destiny", destiny.get("name", "")))
                for label, val in rows:
                    with ui.row().classes('w-full justify-between border-b border-gray-800 py-1'):
                        ui.label(f"{label}:").classes('text-gray-400')
                        ui.label(val).classes('text-white text-sm text-right flex-1')

                if destiny is not None:
                    destiny_subs = [
                        ("Source of Inspiration", destiny.get("src_inspiration", "")),
                        ("Inspiration Feat", destiny.get("inspiration_feat", "")),
                        ("Fulfillment Feat", destiny.get("fullfillment", "")),
                    ]
                    for label, val in destiny_subs:
                        if not val:
                            continue
                        with ui.row().classes('w-full justify-between border-b border-gray-800 py-1 pl-4'):
                            ui.label(f"{label}:").classes('text-gray-500 text-xs')
                            ui.label(val).classes('text-gray-300 text-sm text-right flex-1')

                phys_rows = [
                    ("Title", details.get("title", ""), True),
                    ("Age", details.get("age", ""), True),
                    ("Gender", details.get("gender", ""), True),
                    ("Height", details.get("height", ""), True),
                    ("Weight", details.get("weight", ""), True),
                    ("Eyes", details.get("eyes", ""), True),
                    ("Hair", details.get("hair", ""), True),
                    ("Skin", details.get("skin", ""), True),
                    ("Deity", details.get("deity", ""), True),
                    ("Alignment", details.get("alignment", ""), not hide_alignment),
                ]
                for label, val, visible in phys_rows:
                    if not visible or not val:
                        continue
                    with ui.row().classes('w-full justify-between border-b border-gray-800 py-1'):
                        ui.label(f"{label}:").classes('text-gray-400')
                        ui.label(val).classes('text-white text-sm text-right flex-1')

                rp_rows = [
                    ("Appearance", cs.appearance, True),
                    ("Personality", cs.personality, True),
                    ("Ideals", cs.ideals, not hide_ideals),
                    ("Bonds", cs.bonds, not hide_bonds),
                    ("Flaws", cs.flaws, not hide_flaws),
                    ("Backstory", cs.backstory, True),
                ]
                for label, val, visible in rp_rows:
                    if not visible or not val:
                        continue
                    with ui.column().classes('w-full gap-0 border-b border-gray-800 py-1'):
                        ui.label(f"{label}:").classes('text-gray-400 text-xs')
                        ui.label(val).classes('text-gray-200 text-sm whitespace-pre-wrap')

            with edit_col:
                inp_bg      = ui.input("Background", value=cs.background).classes('w-full').props('dense')
                inp_size    = ui.select(["Tiny","Small","Medium","Large","Huge","Gargantuan"], label="Size", value=cs.size).classes('w-full')
                inp_xp      = ui.number("XP", value=cs.experience_points or 0, step=1, min=0).classes('w-full').props('dense')
                inp_destiny_name = None
                inp_destiny_src = None
                inp_destiny_feat = None
                inp_destiny_full = None
                if destiny is not None:
                    destiny_options = {}

                    async def _load_destiny_options():
                        async with service_session() as s:
                            rows = await list_destinies(s, SheetStyle(cs.style), cs.owner_id)
                        for r in rows:
                            destiny_options[r.name] = {
                                "src_inspiration": r.src_inspiration or "",
                                "inspiration_feat": r.inspiration_feat or "",
                                "fullfillment": r.fullfillment or "",
                            }
                        inp_destiny_name.set_autocomplete(list(destiny_options.keys()))

                    def _on_destiny_select(e):
                        chosen = destiny_options.get(e.value)
                        if chosen:
                            inp_destiny_src.set_value(chosen["src_inspiration"])
                            inp_destiny_feat.set_value(chosen["inspiration_feat"])
                            inp_destiny_full.set_value(chosen["fullfillment"])

                    inp_destiny_name = ui.input(
                        "Destiny", value=cs.destiny.name,
                        on_change=_on_destiny_select,
                    ).classes('w-full').props('dense')
                    with ui.row().classes('w-full gap-2 pl-4'):
                        inp_destiny_src = ui.input("Source of Inspiration", value=cs.destiny.src_inspiration).classes('flex-1').props('dense')
                        inp_destiny_feat = ui.input("Inspiration Feat", value=cs.destiny.inspiration_feat).classes('flex-1').props('dense')
                    with ui.row().classes('w-full pl-4'):
                        inp_destiny_full = ui.input("Fulfillment Feat", value=cs.destiny.fullfillment).classes('flex-1').props('dense')

                    defer_load(_load_destiny_options, delay=0.1)

                ui.separator().classes('my-2')
                ui.label("Physical Description").classes('text-gray-400 text-xs uppercase')
                inp_title   = ui.input("Title", value=details.get("title", "")).classes('w-full').props('dense')
                inp_age     = ui.input("Age", value=details.get("age", "")).classes('w-full').props('dense')
                inp_gender  = ui.input("Gender", value=details.get("gender", "")).classes('w-full').props('dense')
                with ui.row().classes('w-full gap-2'):
                    inp_height = ui.input("Height", value=details.get("height", "")).classes('flex-1').props('dense')
                    inp_weight = ui.input("Weight", value=details.get("weight", "")).classes('flex-1').props('dense')
                with ui.row().classes('w-full gap-2'):
                    inp_eyes = ui.input("Eyes", value=details.get("eyes", "")).classes('flex-1').props('dense')
                    inp_hair = ui.input("Hair", value=details.get("hair", "")).classes('flex-1').props('dense')
                    inp_skin = ui.input("Skin", value=details.get("skin", "")).classes('flex-1').props('dense')
                inp_deity   = ui.input("Deity", value=details.get("deity", "")).classes('w-full').props('dense')
                inp_align   = None if hide_alignment else ui.input("Alignment", value=details.get("alignment", "")).classes('w-full').props('dense')

                ui.separator().classes('my-2')
                ui.label("Roleplaying").classes('text-gray-400 text-xs uppercase')
                inp_appear = ui.textarea("Appearance", value=cs.appearance).classes('w-full').props('dense rows=2')
                inp_pers   = ui.textarea("Personality", value=cs.personality).classes('w-full').props('dense rows=2')
                inp_ideals = None if hide_ideals else ui.textarea("Ideals", value=cs.ideals).classes('w-full').props('dense rows=2')
                inp_bonds  = None if hide_bonds  else ui.textarea("Bonds", value=cs.bonds).classes('w-full').props('dense rows=2')
                inp_flaws  = None if hide_flaws  else ui.textarea("Flaws", value=cs.flaws).classes('w-full').props('dense rows=2')
                inp_back   = ui.textarea("Backstory", value=cs.backstory).classes('w-full').props('dense rows=4')

                async def _save_desc():
                    updates = {
                        "background": inp_bg.value or "Peasant",
                        "size": inp_size.value or "Medium",
                        "experience_points": int(inp_xp.value or 0),
                        "appearance": inp_appear.value or "",
                        "personality": inp_pers.value or "",
                        "backstory": inp_back.value or "",
                        "title": inp_title.value or "",
                        "age": inp_age.value or "",
                        "gender": inp_gender.value or "",
                        "height": inp_height.value or "",
                        "weight": inp_weight.value or "",
                        "eyes": inp_eyes.value or "",
                        "hair": inp_hair.value or "",
                        "skin": inp_skin.value or "",
                        "deity": inp_deity.value or "",
                    }
                    if inp_ideals is not None: updates["ideals"] = inp_ideals.value or ""
                    if inp_bonds  is not None: updates["bonds"]  = inp_bonds.value or ""
                    if inp_flaws  is not None: updates["flaws"]  = inp_flaws.value or ""
                    if inp_align  is not None: updates["alignment"] = inp_align.value or ""
                    if inp_destiny_name is not None:
                        updates["destiny"] = {
                            "name": inp_destiny_name.value or "",
                            "src_inspiration": inp_destiny_src.value or "",
                            "inspiration_feat": inp_destiny_feat.value or "",
                            "fullfillment": inp_destiny_full.value or "",
                        }
                    await _save(updates)

                ui.button("Save", on_click=_save_desc).props('unelevated color=primary').classes('mt-2 w-full')

            edit_col.set_visibility(False)
            edit_btn.on_click(make_toggle_handler(is_editing, display_col, edit_col, edit_btn))

    _section()
    return _section
