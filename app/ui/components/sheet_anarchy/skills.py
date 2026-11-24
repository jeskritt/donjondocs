"""
AI Helper Docstring
Purpose: Shadowrun: Anarchy 2.0 Skills, Specializations (+2), Risk Reduction (RR), and Knowledge Skills card. Groups the 14 skills by category, allows inline Rating +/- (0–8), linked Attribute switching for dual-attribute skills, adding/removing Specializations (from canonical suggestions or custom), and managing Knowledge Skills.
Interactions:
- `app.builders.shadowrun_anarchy`: computes `dp` and `rr` for every skill and specialization.
- `app.services.global_items_service.list_skills`: supplies canonical specialization hints.
"""

from __future__ import annotations

import re

from nicegui import ui

from app.rule_systems import SheetStyle
from app.services.global_items_service import list_skills
from app.services.session import service_session
from app.ui.components.sheet.helpers import render_pm_adjuster
from app.ui.theme import DIALOG_CARD_STYLE, notify_error

_SPEC_TOKEN_RE = re.compile(r"^\s*([^(]+?)\s*(?:\(\+([^)]+)\))?\s*$")


def _parse_canonical_specs(raw: str | None) -> list[tuple[str, str]]:
    """Parse 'climbing (+STR), parkour (+AGI)' -> [('climbing', 'STR'), ('parkour', 'AGI')]."""
    if not raw:
        return []
    out: list[tuple[str, str]] = []
    for part in raw.split(","):
        m = _SPEC_TOKEN_RE.match(part.strip())
        if not m:
            continue
        name = m.group(1).strip()
        attr = (m.group(2) or "").split("/")[0].strip().upper()
        if name:
            out.append((name, attr))
    return out


def _render_anarchy_skills(state, char_id, user, _save):
    """Render the Skills, Specializations & Knowledge Skills card."""

    async def _bump_skill_rating(skill_idx: int, delta: int):
        skills = [s.model_dump() for s in state["cs"].skills]
        cur = int(skills[skill_idx]["rating"])
        new_val = max(0, min(8, cur + delta))
        if new_val != cur:
            skills[skill_idx]["rating"] = new_val
            await _save({"skills": skills})

    async def _change_skill_attr(skill_idx: int, new_attr: str):
        skills = [s.model_dump() for s in state["cs"].skills]
        skills[skill_idx]["attribute"] = new_attr
        await _save({"skills": skills})

    async def _delete_spec(skill_idx: int, spec_idx: int):
        skills = [s.model_dump() for s in state["cs"].skills]
        skills[skill_idx]["specializations"].pop(spec_idx)
        await _save({"skills": skills})

    async def _open_add_spec(skill_idx: int):
        sk = state["cs"].skills[skill_idx]
        if sk.rating < 1:
            notify_error("A Skill must be at least Rating 1 before adding a Specialization.")
            return
        async with service_session() as session:
            g_rows = await list_skills(session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=user.id)
        match = next((r for r in g_rows if r.name.lower() == sk.name.lower()), None)
        suggestions = _parse_canonical_specs(match.specialties if match else None)
        sugg_map = {n: a for n, a in suggestions}

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-md").style(DIALOG_CARD_STYLE):
            ui.label(f"Add Specialization — {sk.name}").classes("text-lg font-bold text-white mb-2")
            spec_select = ui.select(
                options=["Custom…"] + list(sugg_map.keys()),
                value="Custom…",
                label="Canonical Specialization (optional)",
            ).props("dense outlined dark").classes("w-full")
            name_in = ui.input("Specialization Name").props("dense outlined dark").classes("w-full mt-2")
            attr_in = ui.select(
                options=["STR", "AGI", "WIL", "LOG", "CHA"],
                value=sk.attribute,
                label="Linked Attribute",
            ).props("dense outlined dark").classes("w-full mt-2")

            def _pick_sugg(_=None):
                val = spec_select.value
                if val and val != "Custom…":
                    name_in.set_value(val)
                    if sugg_map.get(val) in {"STR", "AGI", "WIL", "LOG", "CHA"}:
                        attr_in.set_value(sugg_map[val])

            spec_select.on_value_change(_pick_sugg)

            async def _commit():
                nm = (name_in.value or "").strip()
                if not nm:
                    notify_error("Specialization name is required.")
                    return
                skills = [s.model_dump() for s in state["cs"].skills]
                skills[skill_idx]["specializations"].append({
                    "name": nm,
                    "attribute": attr_in.value or sk.attribute,
                    "bonus": 2,
                })
                await _save({"skills": skills})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Add (+2)", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    def _open_add_knowledge():
        with ui.dialog() as dlg, ui.card().classes("w-full max-w-sm").style(DIALOG_CARD_STYLE):
            ui.label("Add Knowledge Skill").classes("text-lg font-bold text-white mb-2")
            k_in = ui.input("Knowledge / Language (2,500¥)").props("dense outlined dark").classes("w-full")

            async def _commit():
                val = (k_in.value or "").strip()
                if not val:
                    notify_error("Enter a knowledge skill or language.")
                    return
                ks = list(state["cs"].knowledge_skills) + [val]
                await _save({"knowledge_skills": ks})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Add", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    async def _remove_knowledge(idx: int):
        ks = list(state["cs"].knowledge_skills)
        ks.pop(idx)
        await _save({"knowledge_skills": ks})

    @ui.refreshable
    def _section():
        vd = state["vd"]
        skills = vd.get("skills", [])
        categories = vd.get("skill_categories", [])
        knowledge = vd.get("knowledge_skills", [])

        with ui.card().classes("flex-[2] min-w-[380px]"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Skills & Specializations").classes("text-lg font-bold text-white")
                ui.label("Rating + Attr = DP  |  RR").classes("text-xs text-gray-400 font-mono")

            for cat in categories:
                cat_skills = [s for s in skills if s.get("category") == cat]
                if not cat_skills:
                    continue
                ui.label(cat.upper()).classes("text-xs font-bold tracking-wider text-cyan-400 mt-2 mb-1")
                for sk in cat_skills:
                    with ui.column().classes("w-full gap-0 border-b border-gray-800/80 py-1"):
                        with ui.row().classes("w-full items-center justify-between gap-2"):
                            with ui.row().classes("items-center gap-2 flex-1 min-w-0"):
                                name_cls = "text-sm font-semibold text-white" if sk["rating"] > 0 else "text-sm text-gray-400"
                                lbl = ui.label(sk["name"]).classes(name_cls)
                                if sk.get("example_uses"):
                                    lbl.tooltip(sk["example_uses"])
                                if sk.get("counts_as_knowledge"):
                                    ui.badge("Know", color="teal-9").classes("text-[10px]").tooltip("Rating 4+ counts as a Knowledge Skill")

                            with ui.row().classes("items-center gap-2"):
                                # Rating + +/-
                                ui.label(str(sk["rating"])).classes("font-mono text-sm font-bold text-white w-4 text-right")
                                render_pm_adjuster(
                                    lambda d, i=sk["index"]: _bump_skill_rating(i, d),
                                    minus_tooltip="Decrease rating",
                                    plus_tooltip="Increase rating (max 8)",
                                )
                                # Attribute selector (interactive if multi-attr, badge otherwise)
                                all_attrs = [sk["attribute"]] + [a for a in sk.get("alt_attributes", []) if a != sk["attribute"]]
                                if len(all_attrs) > 1:
                                    ui.select(
                                        options=all_attrs,
                                        value=sk["attribute"],
                                        on_change=lambda e, i=sk["index"]: _change_skill_attr(i, str(e.value)),
                                    ).props("dense borderless dark").classes("w-16 text-xs")
                                else:
                                    ui.badge(sk["attribute"], color="grey-9").classes("font-mono text-xs w-12 justify-center")

                                # DP & RR
                                ui.badge(f"DP {sk['dp']}", color="indigo-8").classes("font-mono text-xs w-14 justify-center")
                                rr_color = "emerald-8" if sk["rr"] > 0 else "grey-9"
                                ui.badge(f"RR {sk['rr']}", color=rr_color).classes("font-mono text-xs w-12 justify-center")

                                ui.button(
                                    icon="add_circle_outline",
                                    on_click=lambda i=sk["index"]: _open_add_spec(i),
                                ).props("flat round dense size=sm").classes("text-cyan-400").tooltip("Add Specialization (+2)")

                        # Specialization sub-rows
                        for sp in sk.get("specializations", []):
                            with ui.row().classes("w-full items-center justify-between pl-5 py-0.5 text-xs"):
                                ui.label(f"↳ ({sp['name']} +{sp['bonus']})").classes("text-cyan-200")
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge(sp["attribute"], color="grey-9").classes("font-mono text-[11px] w-10 justify-center")
                                    ui.badge(f"DP {sp['dp']}", color="cyan-9").classes("font-mono text-[11px] w-14 justify-center")
                                    sp_rr_col = "emerald-7" if sp["rr"] > 0 else "grey-9"
                                    ui.badge(f"RR {sp['rr']}", color=sp_rr_col).classes("font-mono text-[11px] w-12 justify-center")
                                    ui.button(
                                        icon="close",
                                        on_click=lambda si=sk["index"], spi=sp["index"]: _delete_spec(si, spi),
                                    ).props("flat round dense size=xs").classes("text-red-400")

            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between mb-1"):
                ui.label("Knowledge Skills & Languages").classes("text-sm font-semibold text-gray-200")
                ui.button("Add", icon="add", on_click=_open_add_knowledge).props("flat dense").classes("text-cyan-300 text-xs")

            if not knowledge:
                ui.label("None added yet (Keywords and Rating 4+ Skills also apply).").classes("text-xs text-gray-500 italic")
            else:
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    for idx, item in enumerate(knowledge):
                        with ui.row().classes("items-center gap-1 px-2 py-0.5 rounded bg-gray-800 border border-gray-700"):
                            ui.label(item).classes("text-xs text-gray-200")
                            ui.button(
                                icon="close",
                                on_click=lambda i=idx: _remove_knowledge(i),
                            ).props("flat round dense size=xs").classes("text-gray-400")

    _section()
    return _section
