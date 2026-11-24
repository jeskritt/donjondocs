"""
AI Helper Docstring
Purpose: Shadowrun: Anarchy 2.0 Attributes, Essence, and Nuyen Audit card. Renders STR/AGI/WIL/LOG/CHA with inline +/- adjusters clamped to metatype limits, displays Racial Quality, Essence penalty alerts, and total invested Nuyen value (p. 85 cheat sheet).
Interactions:
- `app.builders.shadowrun_anarchy`: provides `attributes`, `essence`, `nuyen_audit`, `top_bar.racial_quality`.
"""

from __future__ import annotations

from nicegui import ui

from app.ui.components.sheet.helpers import render_pm_adjuster


def _render_anarchy_attributes(state, char_id, user, _save):
    """Render the Attributes, Essence & Nuyen Audit card."""

    async def _bump_attr(field: str, max_val: int, delta: int):
        cur = int(getattr(state["cs"], field))
        new_val = max(1, min(max_val, cur + delta))
        if new_val != cur:
            await _save({field: new_val})

    @ui.refreshable
    def _section():
        vd = state["vd"]
        attrs = vd.get("attributes", [])
        essence = vd.get("essence", {})
        audit = vd.get("nuyen_audit", {})
        top = vd.get("top_bar", {})

        with ui.card().classes("flex-1 min-w-[280px]"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Attributes").classes("text-lg font-bold text-white")
                ui.label(f"Racial: {top.get('racial_quality', 'None')}").classes("text-xs text-cyan-300")

            for a in attrs:
                with ui.row().classes("w-full items-center justify-between py-1 border-b border-gray-800"):
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(a["code"], color="cyan-9").classes("font-mono text-xs w-10 justify-center")
                        ui.label(a["label"]).classes("text-sm text-gray-200")
                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"{a['value']} / {a['max']}").classes("text-base font-bold text-white font-mono w-12 text-right")
                        render_pm_adjuster(
                            lambda d, f=a["field"], mx=a["max"]: _bump_attr(f, mx, d),
                            minus_tooltip=f"Decrease {a['code']}",
                            plus_tooltip=f"Increase {a['code']} (cap {a['max']})",
                        )

            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Essence").classes("text-sm font-semibold text-gray-200")
                ess_cls = "text-lg font-bold text-red-400" if essence.get("is_critical") else "text-lg font-bold text-cyan-300"
                ui.label(f"{essence.get('display', '6')} / 6").classes(ess_cls)

            penalties = essence.get("penalties") or []
            if penalties:
                with ui.column().classes("w-full gap-1 mt-1 p-2 rounded bg-red-950/40 border border-red-900/50"):
                    for p in penalties:
                        ui.label(f"• {p}").classes("text-xs text-red-300")
            else:
                ui.label("No Essence penalties active.").classes("text-xs text-gray-500")

            ui.separator().classes("my-3")
            with ui.expansion(
                f"Character Value: {int(audit.get('total', 0)):,}¥",
                icon="payments",
            ).props("dense").classes("w-full text-xs text-gray-300"):
                with ui.column().classes("w-full gap-1 pt-1"):
                    for lbl, key in (
                        ("Attributes", "attributes"),
                        ("Skills, Specs & Knowledge", "skills"),
                        ("Shadow Amps", "shadow_amps"),
                        ("Weapons, Armor, Spells & Gear", "gear_and_spells"),
                    ):
                        with ui.row().classes("w-full justify-between text-xs"):
                            ui.label(lbl).classes("text-gray-400")
                            ui.label(f"{int(audit.get(key, 0)):,}¥").classes("text-amber-300 font-mono")

    _section()
    return _section
