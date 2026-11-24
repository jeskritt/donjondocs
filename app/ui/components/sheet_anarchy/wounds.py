"""
AI Helper Docstring
Purpose: Shadowrun: Anarchy 2.0 Wounds, Condition Monitor, Wound Thresholds, and Armor card. Provides interactive Light/Serious/Incapacitated wound checkboxes, Stim Patch toggle, active Disadvantage banner, auto-derived Threshold table (No Armor / Main / Alternate / Mental), and Armor library/custom picker.
Interactions:
- `app.builders.shadowrun_anarchy`: provides `wounds` and `armor`.
- `app.services.global_items_service.list_armor`: populates standard armor picker.
"""

from __future__ import annotations

import uuid

from nicegui import ui

from app.rule_systems import SheetStyle
from app.services.global_items_service import list_armor
from app.services.session import service_session
from app.ui.theme import DIALOG_CARD_STYLE, notify_error


def _render_anarchy_wounds(state, char_id, user, _save):
    """Render the Wounds, Thresholds, and Armor card."""

    async def _toggle_light(idx: int, checked: bool):
        w = state["cs"].wounds.model_dump()
        boxes = list(state["vd"]["wounds"]["light_boxes"])
        boxes[idx] = bool(checked)
        w["light"] = boxes
        await _save({"wounds": w})

    async def _toggle_serious(idx: int, checked: bool):
        w = state["cs"].wounds.model_dump()
        boxes = list(state["vd"]["wounds"]["serious_boxes"])
        boxes[idx] = bool(checked)
        w["serious"] = boxes
        await _save({"wounds": w})

    async def _toggle_incap(checked: bool):
        w = state["cs"].wounds.model_dump()
        w["incapacitated"] = bool(checked)
        await _save({"wounds": w})

    async def _toggle_stim(checked: bool):
        w = state["cs"].wounds.model_dump()
        w["stim_patch_active"] = bool(checked)
        await _save({"wounds": w})

    async def _set_armor_slot(idx: int, new_slot: str):
        items = [a.model_dump() for a in state["cs"].armor]
        # Only one Main and one Alternate armor at a time.
        if new_slot in ("main", "alternate"):
            for i, it in enumerate(items):
                if i != idx and it["slot"] == new_slot:
                    it["slot"] = "inactive"
        items[idx]["slot"] = new_slot
        await _save({"armor": items})

    async def _delete_armor(idx: int):
        items = [a.model_dump() for a in state["cs"].armor]
        items.pop(idx)
        await _save({"armor": items})

    async def _open_add_armor():
        async with service_session() as session:
            lib_rows = await list_armor(session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=user.id)

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-md").style(DIALOG_CARD_STYLE):
            ui.label("Add Armor").classes("text-lg font-bold text-white mb-2")
            lib_map = {r.name: r for r in lib_rows}
            lib_select = ui.select(
                options=["Custom…"] + list(lib_map.keys()),
                value="Custom…",
                label="Pick from Library (optional)",
            ).props("dense outlined dark").classes("w-full")

            name_in = ui.input("Armor Name").props("dense outlined dark").classes("w-full mt-2")
            with ui.row().classes("w-full gap-2 mt-2"):
                rating_in = ui.number("Armor Rating", value=3, min=0, max=10, step=1).props("dense outlined dark").classes("flex-1")
                slot_in = ui.select(
                    options={"main": "Main Armor", "alternate": "Alternate Armor", "inactive": "Inactive"},
                    value="main",
                    label="Slot",
                ).props("dense outlined dark").classes("flex-1")
            notes_in = ui.input("Notes").props("dense outlined dark").classes("w-full mt-2")

            def _apply_preset(_=None):
                row = lib_map.get(lib_select.value)
                if row is not None:
                    name_in.set_value(row.name)
                    rating_in.set_value(row.base_ac if row.base_ac is not None else 1)
                    notes_in.set_value(row.notes or "")

            lib_select.on_value_change(_apply_preset)

            async def _commit():
                nm = (name_in.value or "").strip()
                if not nm:
                    notify_error("Armor name is required.")
                    return
                slot = slot_in.value or "inactive"
                items = [a.model_dump() for a in state["cs"].armor]
                if slot in ("main", "alternate"):
                    for it in items:
                        if it["slot"] == slot:
                            it["slot"] = "inactive"
                items.append({
                    "id": str(uuid.uuid4()),
                    "name": nm,
                    "rating": int(rating_in.value or 0),
                    "slot": slot,
                    "notes": (notes_in.value or "").strip(),
                    "is_custom": lib_select.value == "Custom…",
                })
                await _save({"armor": items})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Add", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    @ui.refreshable
    def _section():
        vd = state["vd"]
        w = vd.get("wounds", {})
        armors = vd.get("armor", [])

        with ui.card().classes("flex-1 min-w-[320px]"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Condition Monitor & Wounds").classes("text-lg font-bold text-white")
                ui.switch(
                    "Stim Patch",
                    value=bool(w.get("stim_patch_active", False)),
                    on_change=lambda e: _toggle_stim(bool(e.value)),
                ).props("dense color=amber").classes("text-xs text-amber-300")

            # Condition Monitor checkboxes
            with ui.row().classes("w-full items-center gap-4 flex-wrap py-1"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Light:").classes("text-xs font-semibold text-amber-300 mr-1")
                    for idx, checked in enumerate(w.get("light_boxes", [])):
                        ui.checkbox(
                            f"L{idx + 1}",
                            value=checked,
                            on_change=lambda e, i=idx: _toggle_light(i, bool(e.value)),
                        ).props("dense color=amber")

                with ui.row().classes("items-center gap-1"):
                    ui.label("Serious:").classes("text-xs font-semibold text-red-400 mr-1")
                    for idx, checked in enumerate(w.get("serious_boxes", [])):
                        ui.checkbox(
                            f"S{idx + 1}",
                            value=checked,
                            on_change=lambda e, i=idx: _toggle_serious(i, bool(e.value)),
                        ).props("dense color=red")

                ui.checkbox(
                    "Incapacitated",
                    value=bool(w.get("incapacitated", False)),
                    on_change=lambda e: _toggle_incap(bool(e.value)),
                ).props("dense color=deep-orange")

            if w.get("penalty_note"):
                banner_cls = (
                    "bg-red-950/60 border-red-700 text-red-200"
                    if w.get("status_severity") in ("danger", "critical")
                    else "bg-amber-950/50 border-amber-700 text-amber-200"
                )
                with ui.row().classes(f"w-full p-2 mt-1 rounded border text-xs {banner_cls}"):
                    ui.label(w["penalty_note"])

            ui.separator().classes("my-3")
            ui.label("Wound Thresholds").classes("text-sm font-semibold text-gray-200 mb-1")
            cols = [
                {"name": "label", "label": "Protection", "field": "label", "align": "left"},
                {"name": "light", "label": "Light", "field": "light", "align": "center"},
                {"name": "serious", "label": "Serious", "field": "serious", "align": "center"},
                {"name": "incap", "label": "Incap.", "field": "incap", "align": "center"},
            ]
            ui.table(
                columns=cols,
                rows=w.get("thresholds", []),
                row_key="label",
            ).props("dense flat bordered dark hide-bottom").classes("w-full")

            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between mb-1"):
                ui.label("Armor").classes("text-sm font-semibold text-gray-200")
                ui.button("Add Armor", icon="add", on_click=_open_add_armor).props("flat dense").classes("text-cyan-300 text-xs")

            if not armors:
                ui.label("No armor equipped.").classes("text-xs text-gray-500 italic")
            else:
                for ar in armors:
                    with ui.row().classes("w-full items-center justify-between py-1 border-b border-gray-800 gap-2"):
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(f"{ar['name']} (Armor {ar['rating']})").classes("text-sm text-white font-medium")
                            if ar.get("notes"):
                                ui.label(ar["notes"]).classes("text-xs text-gray-400")
                        ui.select(
                            options={"main": "Main", "alternate": "Alt", "inactive": "Off"},
                            value=ar["slot"],
                            on_change=lambda e, i=ar["index"]: _set_armor_slot(i, str(e.value)),
                        ).props("dense outlined dark").classes("w-24")
                        ui.button(
                            icon="delete",
                            on_click=lambda i=ar["index"]: _delete_armor(i),
                        ).props("flat round dense size=sm").classes("text-red-400")

    _section()
    return _section
