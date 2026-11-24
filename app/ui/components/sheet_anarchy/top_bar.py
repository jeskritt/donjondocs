"""
AI Helper Docstring
Purpose: Sticky top bar for Shadowrun: Anarchy 2.0 character sheets. Surfaces Streetname, Metatype, Keywords summary, inline Edge +/- adjuster + New Run reset, Essence badge, Wound status badge, quick Nuyen editor, and a Risk & Glitch Table popup. Intentionally omits the 5e PHB parchment toggle.
Interactions:
- `app.ui.pages.character_sheet`: mounts this top bar when `system_family == sra2`.
- `app.ui.components.anarchy_editor.open_anarchy_character_editor`: edits Streetname/Metatype/Keywords.
"""

from __future__ import annotations

from nicegui import ui

from app.schemas.shadowrun_anarchy import METATYPE_RULES, Metatype
from app.ui.components.anarchy_editor import open_anarchy_character_editor
from app.ui.components.sheet.helpers import render_pm_adjuster
from app.ui.theme import DIALOG_CARD_STYLE


def _render_anarchy_top_bar(state, char_id, user, _save, _apply_rest):
    """Build and return the refreshable Shadowrun: Anarchy 2.0 sticky top bar."""

    async def _edit_identity():
        cs = state["cs"]
        form = await open_anarchy_character_editor(
            initial={
                "name": cs.name,
                "metatype": cs.metatype.value,
                "keywords": list(cs.keywords),
            },
            title="Edit Runner Identity",
            confirm_label="Save",
        )
        if form is None:
            return
        new_meta = Metatype(form["metatype"])
        new_base = int(METATYPE_RULES[new_meta]["edge_base"])
        updates: dict = {
            "name": form["name"],
            "metatype": new_meta.value,
            "keywords": form["keywords"],
        }
        # Update default base Edge when switching metatype (preserving custom overrides otherwise).
        if new_meta != cs.metatype:
            updates["edge_base"] = new_base
            if cs.edge_current == cs.edge_base:
                updates["edge_current"] = new_base
        await _save(updates)

    def _open_nuyen_dialog():
        cs = state["cs"]
        with ui.dialog() as dlg, ui.card().classes("w-full max-w-xs").style(DIALOG_CARD_STYLE):
            ui.label("Edit Nuyen (¥)").classes("text-lg font-bold text-white mb-2")
            ny_in = ui.number(label="Current Nuyen (¥)", value=cs.nuyen, min=0, step=500).props("dense outlined dark").classes("w-full")
            delta_in = ui.number(label="Quick Add / Subtract (±¥)", value=0, step=500).props("dense outlined dark").classes("w-full mt-2")

            async def _commit():
                base_val = int(ny_in.value or 0)
                delta_val = int(delta_in.value or 0)
                await _save({"nuyen": max(0, base_val + delta_val)})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Save", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    def _open_risk_table_dialog():
        vd = state["vd"]
        with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg").style(DIALOG_CARD_STYLE):
            ui.label("Risk Dice & Glitch Table").classes("text-lg font-bold text-cyan-300 mb-2")
            cols = [
                {"name": "rr", "label": "RR", "field": "rr", "align": "center"},
                {"name": "low", "label": "Low", "field": "low", "align": "center"},
                {"name": "normal", "label": "Normal", "field": "normal", "align": "center"},
                {"name": "high", "label": "High", "field": "high", "align": "center"},
                {"name": "extreme", "label": "Extreme", "field": "extreme", "align": "center"},
            ]
            ui.table(columns=cols, rows=vd.get("risk_table", []), row_key="rr").props("dense flat bordered dark hide-bottom").classes("w-full")
            ui.label(vd.get("glitch_scale", "")).classes("text-xs text-gray-300 mt-3")
            with ui.row().classes("w-full justify-end mt-3"):
                ui.button("Close", on_click=dlg.close).props("flat").style("color:#94A3B8;")
        dlg.open()

    async def _adjust_edge(delta: int):
        cur = int(state["cs"].edge_current)
        await _save({"edge_current": max(0, cur + delta)})

    @ui.refreshable
    def _section():
        top = state["vd"].get("top_bar", {})
        sev = top.get("wound_severity", "ok")
        wound_color = {
            "ok": "text-emerald-400",
            "warning": "text-amber-400",
            "danger": "text-red-400",
            "critical": "text-red-500",
        }.get(sev, "text-white")

        with ui.row().classes(
            "w-full sticky top-[60px] z-40 p-2 shadow-md bg-opacity-90 border-b border-cyan-900/60"
        ).style(
            "background-color: #161826; margin-top: -16px; margin-left: -16px; margin-right: -16px; "
            "padding: 1rem; width: calc(100% + 32px);"
        ):
            with ui.row().classes("w-full flex-wrap items-center justify-between gap-4 px-4"):
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(top.get("name", "")).classes("text-3xl font-bold text-white")
                        ui.badge(top.get("metatype", "Human"), color="cyan-8").classes("text-xs")
                        ui.button(icon="edit", on_click=_edit_identity).props("flat round dense").classes("text-gray-400").tooltip("Edit Streetname / Metatype / Keywords")
                    ui.label(top.get("keywords_summary", "")).classes("text-sm text-gray-400")

                with ui.row().classes("gap-6 items-center flex-wrap"):
                    # EDGE with inline +/- adjuster
                    with ui.column().classes("items-center gap-0"):
                        ui.label("EDGE").classes("text-xs text-cyan-400")
                        with ui.row().classes("items-center gap-1"):
                            ui.label(f"{top.get('edge_current', 0)}/{top.get('edge_base', 3)}").classes("text-2xl font-bold text-white")
                            render_pm_adjuster(_adjust_edge, minus_tooltip="Spend 1 Edge", plus_tooltip="Gain 1 Edge")

                    # ESSENCE
                    with ui.column().classes("items-center gap-0"):
                        ui.label("ESSENCE").classes("text-xs text-gray-400")
                        ess_cls = "text-2xl font-bold text-red-400" if top.get("essence_critical") else "text-2xl font-bold text-cyan-300"
                        ui.label(str(top.get("essence_display", "6"))).classes(ess_cls)

                    # WOUNDS status
                    with ui.column().classes("items-center gap-0"):
                        ui.label("WOUNDS").classes("text-xs text-gray-400")
                        ui.label(str(top.get("wound_status", "Healthy"))).classes(f"text-xl font-bold {wound_color}")

                    # NUYEN
                    with ui.column().classes("items-center gap-0 cursor-pointer").on("click", _open_nuyen_dialog).tooltip("Click to adjust Nuyen"):
                        ui.label("NUYEN").classes("text-xs text-gray-400")
                        ui.label(f"{int(top.get('nuyen', 0)):,}¥").classes("text-xl font-bold text-amber-300")

                with ui.row().classes("gap-2 items-center"):
                    ui.button(
                        "New Run",
                        icon="refresh",
                        on_click=lambda: _apply_rest("new_run", {}),
                    ).props("flat dense").classes("text-cyan-300").tooltip("Reset Edge to metatype starting value")
                    ui.button(
                        "Heal All",
                        icon="healing",
                        on_click=lambda: _apply_rest("heal_all", {}),
                    ).props("flat dense").classes("text-emerald-300").tooltip("Clear all wounds (downtime natural healing)")
                    ui.button(
                        "Risk Table",
                        icon="casino",
                        on_click=_open_risk_table_dialog,
                    ).props("outline dense").classes("text-gray-200")

    _section()
    return _section
