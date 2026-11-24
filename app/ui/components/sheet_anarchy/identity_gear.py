"""
AI Helper Docstring
Purpose: Shadowrun: Anarchy 2.0 Roleplay Traits (5 Keywords, 4 Dispositions, 4 Cues), Equipment & Nuyen list, and inline Risk & Glitch Reference Table card.
Interactions:
- `app.services.global_items_service.list_items`: populates standard runner equipment picker.
- `app.builders.shadowrun_anarchy`: provides `keywords`, `dispositions`, `cues`, `equipment`, `risk_table`, `glitch_scale`.
"""

from __future__ import annotations

import uuid

from nicegui import ui

from app.rule_systems import SheetStyle
from app.services.global_items_service import list_items
from app.services.session import service_session
from app.ui.theme import DIALOG_CARD_STYLE, notify_error


def _render_anarchy_identity_gear(state, char_id, user, _save):
    """Render Keywords, Dispositions, Cues, Equipment & Risk Reference card."""

    def _open_traits_dialog():
        cs = state["cs"]
        kws = list(cs.keywords) + [""] * max(0, 5 - len(cs.keywords))
        disps = list(cs.dispositions) + [""] * max(0, 4 - len(cs.dispositions))
        cues = list(cs.cues) + [""] * max(0, 4 - len(cs.cues))

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl").style(DIALOG_CARD_STYLE):
            ui.label("Edit Keywords, Dispositions & Cues").classes("text-lg font-bold text-white mb-2")

            ui.label("Keywords (5)").classes("text-xs font-bold text-cyan-400")
            kw_inputs = [ui.input(f"Keyword {i + 1}", value=kws[i]).props("dense outlined dark").classes("w-full") for i in range(5)]

            ui.label("Dispositions (4 — spend Edge for Advantage, act against self for +1 Edge)").classes("text-xs font-bold text-amber-300 mt-3")
            disp_inputs = [ui.input(f"Disposition {i + 1}", value=disps[i]).props("dense outlined dark").classes("w-full") for i in range(4)]

            ui.label("Cues (4 — signature quotes)").classes("text-xs font-bold text-purple-300 mt-3")
            cue_inputs = [ui.input(f"Cue {i + 1}", value=cues[i]).props("dense outlined dark").classes("w-full") for i in range(4)]

            bio_in = ui.textarea("Background / Bio", value=cs.bio or "").props("dense outlined dark autogrow").classes("w-full mt-3")

            async def _commit():
                await _save({
                    "keywords": [(x.value or "").strip() for x in kw_inputs],
                    "dispositions": [(x.value or "").strip() for x in disp_inputs],
                    "cues": [(x.value or "").strip() for x in cue_inputs],
                    "bio": (bio_in.value or "").strip(),
                })
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Save", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    async def _delete_gear(idx: int):
        items = [g.model_dump() for g in state["cs"].equipment]
        items.pop(idx)
        await _save({"equipment": items})

    async def _open_add_gear():
        async with service_session() as session:
            lib_rows = await list_items(session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=user.id)

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-md").style(DIALOG_CARD_STYLE):
            ui.label("Add Equipment").classes("text-lg font-bold text-white mb-2")
            lib_map = {r.name: r for r in lib_rows}
            lib_select = ui.select(
                options=["Custom…"] + list(lib_map.keys()),
                value="Custom…",
                with_input=True,
                label="Pick from Library (optional)",
            ).props("dense outlined dark").classes("w-full")

            name_in = ui.input("Item Name*").props("dense outlined dark").classes("w-full mt-2")
            with ui.row().classes("w-full gap-2 mt-2"):
                cat_in = ui.input("Category", value="Gear").props("dense outlined dark").classes("flex-1")
                cost_in = ui.number("Cost (¥)", value=2500, min=0, step=500).props("dense outlined dark").classes("flex-1")
            notes_in = ui.input("Notes / Effect").props("dense outlined dark").classes("w-full mt-2")

            def _apply_gear(_=None):
                row = lib_map.get(lib_select.value)
                if row is None:
                    return
                name_in.set_value(row.name)
                cat_in.set_value(row.type or "Gear")
                raw_cost = (row.value or "2500").replace(",", "").replace("¥", "").strip()
                try:
                    cost_in.set_value(int(raw_cost))
                except ValueError:
                    cost_in.set_value(2500)
                notes_in.set_value(row.effects or row.description or "")

            lib_select.on_value_change(_apply_gear)

            async def _commit():
                nm = (name_in.value or "").strip()
                if not nm:
                    notify_error("Item name is required.")
                    return
                items = [g.model_dump() for g in state["cs"].equipment]
                items.append({
                    "id": str(uuid.uuid4()),
                    "name": nm,
                    "category": (cat_in.value or "Gear").strip(),
                    "cost": int(cost_in.value or 0),
                    "notes": (notes_in.value or "").strip(),
                    "is_custom": lib_select.value == "Custom…",
                })
                await _save({"equipment": items})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Add", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    @ui.refreshable
    def _section():
        vd = state["vd"]
        kws = [k for k in vd.get("keywords", []) if k]
        disps = [d for d in vd.get("dispositions", []) if d]
        cues = [c for c in vd.get("cues", []) if c]
        gear = vd.get("equipment", [])
        bio = vd.get("bio", "")

        with ui.card().classes("flex-1 min-w-[320px]"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Keywords, Dispositions & Cues").classes("text-lg font-bold text-white")
                ui.button("Edit", icon="edit", on_click=_open_traits_dialog).props("flat dense").classes("text-cyan-300 text-xs")

            ui.label("KEYWORDS").classes("text-xs font-bold tracking-wider text-cyan-400")
            if kws:
                with ui.row().classes("w-full gap-1.5 flex-wrap my-1"):
                    for k in kws:
                        ui.badge(k, color="cyan-9").classes("text-xs py-1 px-2")
            else:
                ui.label("Click Edit to add 5 Keywords.").classes("text-xs text-gray-500 italic my-1")

            ui.label("DISPOSITIONS").classes("text-xs font-bold tracking-wider text-amber-300 mt-2")
            if disps:
                with ui.row().classes("w-full gap-1.5 flex-wrap my-1"):
                    for d in disps:
                        ui.badge(d, color="amber-9").classes("text-xs py-1 px-2")
            else:
                ui.label("No Dispositions yet.").classes("text-xs text-gray-500 italic my-1")

            ui.label("CUES").classes("text-xs font-bold tracking-wider text-purple-300 mt-2")
            if cues:
                with ui.column().classes("w-full gap-1 my-1"):
                    for c in cues:
                        ui.label(f"“{c}”").classes("text-xs italic text-gray-200 pl-2 border-l-2 border-purple-700")
            else:
                ui.label("No Cues yet.").classes("text-xs text-gray-500 italic my-1")

            if bio:
                ui.separator().classes("my-2")
                ui.label(bio).classes("text-xs text-gray-300 whitespace-pre-wrap")

            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between mb-1"):
                ui.label("Equipment").classes("text-sm font-semibold text-gray-200")
                ui.button("Add Gear", icon="add", on_click=_open_add_gear).props("flat dense").classes("text-cyan-300 text-xs")

            if not gear:
                ui.label("No equipment listed.").classes("text-xs text-gray-500 italic")
            else:
                for g in gear:
                    with ui.row().classes("w-full items-center justify-between py-1 border-b border-gray-800 gap-2"):
                        with ui.column().classes("gap-0 flex-1"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(g["name"]).classes("text-sm text-white font-medium")
                                ui.badge(g["category"], color="grey-9").classes("text-[10px]")
                            if g.get("notes"):
                                ui.label(g["notes"]).classes("text-xs text-gray-400")
                        ui.button(
                            icon="delete",
                            on_click=lambda i=g["index"]: _delete_gear(i),
                        ).props("flat round dense size=xs").classes("text-red-400")

            ui.separator().classes("my-3")
            with ui.expansion("Risk Dice & Glitch Table", icon="casino").props("dense").classes("w-full text-xs text-cyan-300"):
                cols = [
                    {"name": "rr", "label": "RR", "field": "rr", "align": "center"},
                    {"name": "low", "label": "Low", "field": "low", "align": "center"},
                    {"name": "normal", "label": "Normal", "field": "normal", "align": "center"},
                    {"name": "high", "label": "High", "field": "high", "align": "center"},
                    {"name": "extreme", "label": "Extreme", "field": "extreme", "align": "center"},
                ]
                ui.table(columns=cols, rows=vd.get("risk_table", []), row_key="rr").props("dense flat bordered dark hide-bottom").classes("w-full mt-1")
                ui.label(vd.get("glitch_scale", "")).classes("text-[11px] text-gray-400 mt-1")

    _section()
    return _section
