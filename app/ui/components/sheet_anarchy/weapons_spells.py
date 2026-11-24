"""
AI Helper Docstring
Purpose: Shadowrun: Anarchy 2.0 Weapons & Spells card (mirroring p. 322). Renders Weapons with dynamically evaluated DV (`STR+X`) and four color-coded range pills (`Close / Short / Med / Long`), plus Spells with category, Instant/Sustained badge, threshold, and a play-time Sustaining toggle.
Interactions:
- `app.services.global_items_service.{list_weapons, list_spells}`: populates library pickers.
- `app.builders.shadowrun_anarchy`: provides `weapons`, `spells`, `sustained_spell_count`.
"""

from __future__ import annotations

import uuid

from nicegui import ui

from app.rule_systems import SheetStyle
from app.services.global_items_service import list_spells, list_weapons
from app.services.session import service_session
from app.ui.theme import DIALOG_CARD_STYLE, notify_error

_RANGE_OPTIONS = ["OK", "Dis.", "—"]


def _range_badge_color(val: str) -> str:
    if val == "OK":
        return "emerald-8"
    if val.startswith("Dis"):
        return "amber-8"
    return "grey-9"


def _render_anarchy_weapons_spells(state, char_id, user, _save):
    """Render the Weapons & Spells card."""

    async def _delete_weapon(idx: int):
        items = [w.model_dump() for w in state["cs"].weapons]
        items.pop(idx)
        await _save({"weapons": items})

    async def _delete_spell(idx: int):
        items = [s.model_dump() for s in state["cs"].spells]
        items.pop(idx)
        await _save({"spells": items})

    async def _toggle_sustained(idx: int, active: bool):
        items = [s.model_dump() for s in state["cs"].spells]
        items[idx]["sustained_active"] = bool(active)
        await _save({"spells": items})

    async def _open_add_weapon():
        async with service_session() as session:
            lib_rows = await list_weapons(session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=user.id)

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg").style(DIALOG_CARD_STYLE):
            ui.label("Add Weapon").classes("text-lg font-bold text-white mb-2")
            lib_map = {r.name: r for r in lib_rows}
            lib_select = ui.select(
                options=["Custom…"] + list(lib_map.keys()),
                value="Custom…",
                with_input=True,
                label="Pick from Library (optional)",
            ).props("dense outlined dark").classes("w-full")

            with ui.row().classes("w-full gap-2 mt-2"):
                name_in = ui.input("Weapon Name*").props("dense outlined dark").classes("flex-[2]")
                type_in = ui.select(["Weapon", "Spec. weapon", "Unarmed"], value="Weapon", label="Class").props("dense outlined dark").classes("flex-1")

            with ui.row().classes("w-full gap-2 mt-2"):
                dv_in = ui.input("DV (e.g. 5 or STR+1)", value="5").props("dense outlined dark").classes("flex-1")
                skill_in = ui.input("Skill", value="Ranged Weapons").props("dense outlined dark").classes("flex-1")

            ui.label("Range Bands (Close / Short / Medium / Long)").classes("text-xs text-gray-400 mt-2")
            with ui.row().classes("w-full gap-2"):
                r_close = ui.select(_RANGE_OPTIONS, value="OK", label="Close").props("dense outlined dark").classes("flex-1")
                r_short = ui.select(_RANGE_OPTIONS, value="OK", label="Short").props("dense outlined dark").classes("flex-1")
                r_med = ui.select(_RANGE_OPTIONS, value="Dis.", label="Med").props("dense outlined dark").classes("flex-1")
                r_long = ui.select(_RANGE_OPTIONS, value="—", label="Long").props("dense outlined dark").classes("flex-1")

            notes_in = ui.input("Notes").props("dense outlined dark").classes("w-full mt-2")

            def _apply_weapon(_=None):
                row = lib_map.get(lib_select.value)
                if row is None:
                    return
                name_in.set_value(row.name)
                type_in.set_value(row.type if row.type in {"Weapon", "Spec. weapon", "Unarmed"} else "Weapon")
                dv_in.set_value(row.damage or "STR")
                parts = [p.strip() for p in (row.range or "OK/—/—/—").split("/")]
                while len(parts) < 4:
                    parts.append("—")
                for widget, val in zip((r_close, r_short, r_med, r_long), parts):
                    norm = "—" if val in {"-", "–", "—"} else val
                    widget.set_value(norm if norm in _RANGE_OPTIONS else "—")
                notes_in.set_value(row.description or row.notes or "")

            lib_select.on_value_change(_apply_weapon)

            async def _commit():
                nm = (name_in.value or "").strip()
                if not nm:
                    notify_error("Weapon name is required.")
                    return
                items = [w.model_dump() for w in state["cs"].weapons]
                items.append({
                    "id": str(uuid.uuid4()),
                    "name": nm,
                    "weapon_type": type_in.value or "Weapon",
                    "dv": (dv_in.value or "STR").strip(),
                    "range_close": r_close.value or "—",
                    "range_short": r_short.value or "—",
                    "range_medium": r_med.value or "—",
                    "range_long": r_long.value or "—",
                    "skill": (skill_in.value or "Ranged Weapons").strip(),
                    "specialization": "",
                    "notes": (notes_in.value or "").strip(),
                    "is_custom": lib_select.value == "Custom…",
                })
                await _save({"weapons": items})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Add", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    async def _open_add_spell():
        async with service_session() as session:
            lib_rows = await list_spells(session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=user.id)

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg").style(DIALOG_CARD_STYLE):
            ui.label("Add Spell (5,000¥)").classes("text-lg font-bold text-white mb-2")
            lib_map = {r.name: r for r in lib_rows}
            lib_select = ui.select(
                options=["Custom…"] + list(lib_map.keys()),
                value="Custom…",
                with_input=True,
                label="Pick from Spell Library (optional)",
            ).props("dense outlined dark").classes("w-full")

            with ui.row().classes("w-full gap-2 mt-2"):
                name_in = ui.input("Spell Name*").props("dense outlined dark").classes("flex-[2]")
                cat_in = ui.select(["Combat", "Detection", "Health", "Illusion", "Manipulation"], value="Combat", label="Category").props("dense outlined dark").classes("flex-1")

            with ui.row().classes("w-full gap-2 mt-2"):
                sub_in = ui.input("Subtype", placeholder="e.g. Direct / Indirect / Physical").props("dense outlined dark").classes("flex-1")
                dur_in = ui.select({"I": "Instant (I)", "S": "Sustained (S)"}, value="I", label="Duration").props("dense outlined dark").classes("flex-1")
                thr_in = ui.input("Threshold / Opposed", placeholder="e.g. 0, Area, WIL+CHA").props("dense outlined dark").classes("flex-1")

            notes_in = ui.textarea("Effect Notes").props("dense outlined dark autogrow").classes("w-full mt-2")

            def _apply_spell(_=None):
                row = lib_map.get(lib_select.value)
                if row is None:
                    return
                name_in.set_value(row.name)
                if row.school in {"Combat", "Detection", "Health", "Illusion", "Manipulation"}:
                    cat_in.set_value(row.school)
                sub_in.set_value(row.level or "")
                dur_in.set_value("S" if (row.duration or "").upper().startswith("S") else "I")
                thr_in.set_value(row.casting_time or "")
                notes_in.set_value(row.description or "")

            lib_select.on_value_change(_apply_spell)

            async def _commit():
                nm = (name_in.value or "").strip()
                if not nm:
                    notify_error("Spell name is required.")
                    return
                items = [s.model_dump() for s in state["cs"].spells]
                items.append({
                    "id": str(uuid.uuid4()),
                    "name": nm,
                    "category": cat_in.value or "Combat",
                    "subtype": (sub_in.value or "").strip(),
                    "duration": "S" if dur_in.value == "S" else "I",
                    "threshold": (thr_in.value or "").strip(),
                    "sustained_active": False,
                    "notes": (notes_in.value or "").strip(),
                    "is_custom": lib_select.value == "Custom…",
                })
                await _save({"spells": items})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Add", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    @ui.refreshable
    def _section():
        vd = state["vd"]
        weapons = vd.get("weapons", [])
        spells = vd.get("spells", [])
        sustained_count = vd.get("sustained_spell_count", 0)

        with ui.card().classes("flex-1 min-w-[340px]"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Weapons & Spells").classes("text-lg font-bold text-white")
                with ui.row().classes("gap-1"):
                    ui.button("Add Weapon", icon="add", on_click=_open_add_weapon).props("flat dense").classes("text-cyan-300 text-xs")
                    ui.button("Add Spell", icon="auto_fix_high", on_click=_open_add_spell).props("flat dense").classes("text-purple-300 text-xs")

            # Weapons
            ui.label("WEAPONS").classes("text-xs font-bold tracking-wider text-cyan-400 mb-1")
            if not weapons:
                ui.label("No weapons equipped.").classes("text-xs text-gray-500 italic")
            else:
                for w in weapons:
                    with ui.column().classes("w-full gap-1 py-1.5 border-b border-gray-800"):
                        with ui.row().classes("w-full items-center justify-between gap-2"):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.label(w["name"]).classes("text-sm font-semibold text-white")
                                ui.badge(f"DV {w['dv_computed']}", color="red-9").classes("font-mono text-xs")
                                if w["dv_raw"] != w["dv_computed"]:
                                    ui.label(f"({w['dv_raw']})").classes("text-[11px] text-gray-400")
                                ui.badge(w["weapon_type"], color="grey-9").classes("text-[10px]")
                            ui.button(
                                icon="delete",
                                on_click=lambda i=w["index"]: _delete_weapon(i),
                            ).props("flat round dense size=xs").classes("text-red-400")
                        with ui.row().classes("items-center gap-1 flex-wrap"):
                            for r_lbl, r_val in w["ranges"]:
                                ui.badge(f"{r_lbl}: {r_val}", color=_range_badge_color(r_val)).classes("font-mono text-[10px]")
                        if w.get("notes"):
                            ui.label(w["notes"]).classes("text-xs text-gray-400")

            # Spells
            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between mb-1"):
                ui.label("SPELLS").classes("text-xs font-bold tracking-wider text-purple-300")
                if sustained_count > 0:
                    ui.badge(f"Sustaining: {sustained_count}", color="purple-8").classes("text-[11px]")

            if not spells:
                ui.label("No spells learned (Awakened Sorcery runners add spells here).").classes("text-xs text-gray-500 italic")
            else:
                for sp in spells:
                    with ui.column().classes("w-full gap-0.5 py-1.5 border-b border-gray-800"):
                        with ui.row().classes("w-full items-center justify-between gap-2"):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.label(sp["name"]).classes("text-sm font-semibold text-white")
                                ui.badge(sp["category"], color="purple-9").classes("text-[10px]")
                                ui.badge("Sustained" if sp["duration"] == "S" else "Instant", color="indigo-9").classes("text-[10px]")
                                if sp.get("threshold"):
                                    ui.label(f"Thr: {sp['threshold']}").classes("text-xs text-gray-300")
                            with ui.row().classes("items-center gap-1"):
                                if sp["duration"] == "S":
                                    ui.checkbox(
                                        "Active",
                                        value=bool(sp.get("sustained_active", False)),
                                        on_change=lambda e, i=sp["index"]: _toggle_sustained(i, bool(e.value)),
                                    ).props("dense color=purple").classes("text-xs")
                                ui.button(
                                    icon="delete",
                                    on_click=lambda i=sp["index"]: _delete_spell(i),
                                ).props("flat round dense size=xs").classes("text-red-400")
                        if sp.get("notes"):
                            ui.label(sp["notes"]).classes("text-xs text-gray-400")

    _section()
    return _section
