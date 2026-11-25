"""
AI Helper Docstring
Purpose: Shadowrun: Anarchy 2.0 Shadow Amps card. Lists Amps with Essence cost, Rating (¥ value), structured effect badges, and expandable dark-mode Markdown (`body_md`). Add/Edit modal supports picking from the seeded `GlobalAbility` catalog (Cyberdecks, Vehicles, Drones, Cyberware, Bioware, Adept Powers, Mentor Spirits — copied locally for editing) OR authoring custom Amps with auto-seeded Markdown templates for Cyberdecks, Vehicles/Drones, and Contacts.
Interactions:
- `app.services.global_items_service.list_abilities`: loads prebuilt Shadow Amps.
- `app/ui/components/sheet_anarchy/templates/*.md`: blank stat-block seed templates.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from nicegui import ui

from app.rule_systems import SheetStyle
from app.schemas.ally import AllyCreate
from app.schemas.shadowrun_anarchy import DEFAULT_AMP_ESSENCE, AmpType
from app.services.ally_service import create_ally
from app.services.global_items_service import list_abilities
from app.services.session import service_session
from app.services.stat_block_library import extract_ability_stat_block
from app.ui.theme import DIALOG_CARD_STYLE, notify_error

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
# Blank Markdown templates for inline-edited Amps (Cyberdecks stay inline on
# Shadow Amps; Vehicles/Drones/Contacts default to seeding Allies & Stat Blocks).
_AMP_INLINE_TEMPLATES: dict[str, str] = {
    AmpType.CYBERDECK.value: "cyberdeck_template.md",
}
_AMP_ALLY_TEMPLATES: dict[str, tuple[str, str]] = {
    AmpType.VEHICLE_DRONE.value: ("Vehicle", "vehicle_drone_template.md"),
    AmpType.CONTACT.value: ("Contact", "contact_template.md"),
}

_EFFECT_KINDS = {
    "rr_skill": "RR on Skill",
    "rr_spec": "RR on Specialization",
    "rr_attr": "RR on Attribute",
    "armor_bonus": "Physical Armor +1",
    "light_wound_box": "+1 Light Wound Box",
    "serious_wound_box": "+1 Serious Wound Box",
    "unarmed_dv_bonus": "Unarmed DV Bonus",
    "mental_protection": "Mental Protection Bonus",
    "narrative": "Narrative Effect",
}

_FILTER_GROUPS = [
    "All",
    "Cyber/Bio",
    "Magic/Adept",
    "Deck/Vehicle",
    "Equip/Other",
]


def _read_template_file(fname: str | None) -> str | None:
    if not fname:
        return None
    path = _TEMPLATE_DIR / fname
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _read_amp_template(amp_type: str) -> str | None:
    return _read_template_file(_AMP_INLINE_TEMPLATES.get(amp_type))


def _matches_filter(amp_type: str, group: str) -> bool:
    if group == "All":
        return True
    if group == "Cyber/Bio":
        return amp_type in (AmpType.CYBERWARE.value, AmpType.BIOWARE.value)
    if group == "Magic/Adept":
        return amp_type in (AmpType.AWAKENED.value, AmpType.ADEPT_POWER.value)
    if group == "Deck/Vehicle":
        return amp_type in (AmpType.CYBERDECK.value, AmpType.VEHICLE_DRONE.value)
    return amp_type in (AmpType.EQUIPMENT.value, AmpType.QUALITY.value, AmpType.CONTACT.value)


def _render_anarchy_shadow_amps(state, char_id, user, _save):
    """Render the Shadow Amps card."""
    state.setdefault("anarchy_amp_filter", "All")
    state.setdefault("anarchy_amps_expanded", set())

    async def _delete_amp(idx: int):
        amps = [a.model_dump() for a in state["cs"].shadow_amps]
        amps.pop(idx)
        await _save({"shadow_amps": amps})

    async def _open_amp_editor(existing_idx: int | None = None):
        is_new = existing_idx is None
        existing = state["cs"].shadow_amps[existing_idx] if not is_new else None

        lib_rows = []
        if is_new:
            async with service_session() as session:
                all_abilities = await list_abilities(session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=user.id)
            # Exclude Allies-only presets (Spirits, NPC Threats) from the Amp picker.
            lib_rows = [r for r in all_abilities if not extract_ability_stat_block(r)["stat_block_only"]]

        effects_state: list[dict] = (
            [e.model_dump() for e in existing.effects] if existing else []
        )
        # Tracks optional prebuilt Allies stat block when adding a Vehicle/Drone/Contact Amp.
        pending_ally: dict[str, str] = {"ally_type": "", "stat_block_md": ""}

        with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl").style(DIALOG_CARD_STYLE):
            ui.label("Add Shadow Amp" if is_new else f"Edit Shadow Amp — {existing.name}").classes(
                "text-lg font-bold text-white mb-2"
            )

            lib_select = None
            if is_new and lib_rows:
                lib_map = {r.name: r for r in lib_rows}
                lib_select = ui.select(
                    options=["Custom…"] + list(lib_map.keys()),
                    value="Custom…",
                    with_input=True,
                    label="Pick Prebuilt Amp / Deck / Vehicle / Drone (copies locally)",
                ).props("dense outlined dark").classes("w-full mb-2")

            with ui.row().classes("w-full gap-2"):
                name_in = ui.input("Amp Name*", value=(existing.name if existing else "")).props("dense outlined dark").classes("flex-[2]")
                type_in = ui.select(
                    options=[t.value for t in AmpType],
                    value=(existing.amp_type.value if existing else AmpType.CYBERWARE.value),
                    label="Type",
                ).props("dense outlined dark").classes("flex-1")

            with ui.row().classes("w-full gap-2 mt-2"):
                rating_in = ui.number("Rating (× 5,000¥)", value=(existing.rating if existing else 1), min=0, max=50, step=1).props("dense outlined dark").classes("flex-1")
                essence_in = ui.number(
                    "Essence Cost",
                    value=(existing.essence_cost if existing else 1.0),
                    min=0.0,
                    max=6.0,
                    step=0.5,
                ).props("dense outlined dark").classes("flex-1")

            body_in = ui.textarea(
                "Details / Inline Markdown (Cyberdecks, Cyberware, Powers, Summaries)",
                value=(existing.body_md if existing else ""),
            ).props("dense outlined dark autogrow").classes("w-full mt-2")
            ui.label("Supports Markdown. Vehicles, Drones, and Contacts can seed a full stat block on Allies & Stat Blocks.").classes("text-xs text-gray-500")

            # Seed-to-Allies checkbox (shown on Add for Vehicles, Drones, and Contacts).
            seed_ally_box = None
            if is_new:
                seed_ally_box = ui.checkbox(
                    "Also create stat block in Allies & Stat Blocks",
                    value=False,
                ).classes("mt-1 text-xs text-cyan-300")
                seed_ally_box.set_visibility(False)

            def _sync_ally_checkbox(chosen_type: str, ally_type: str = "", stat_md: str = ""):
                if seed_ally_box is None:
                    return
                if ally_type and stat_md:
                    pending_ally["ally_type"] = ally_type
                    pending_ally["stat_block_md"] = stat_md
                    seed_ally_box.set_text(f"Also create {ally_type} stat block in Allies & Stat Blocks")
                    seed_ally_box.set_value(True)
                    seed_ally_box.set_visibility(True)
                elif chosen_type in _AMP_ALLY_TEMPLATES:
                    default_type, tmpl_file = _AMP_ALLY_TEMPLATES[chosen_type]
                    pending_ally["ally_type"] = default_type
                    pending_ally["stat_block_md"] = _read_template_file(tmpl_file) or ""
                    seed_ally_box.set_text(f"Also create {default_type} stat block in Allies & Stat Blocks")
                    seed_ally_box.set_value(True)
                    seed_ally_box.set_visibility(True)
                else:
                    pending_ally["ally_type"] = ""
                    pending_ally["stat_block_md"] = ""
                    seed_ally_box.set_value(False)
                    seed_ally_box.set_visibility(False)

            # Structured mechanical modifiers section
            ui.separator().classes("my-2")
            ui.label("Mechanical Effects (auto-applied to Skills, Wounds, Armor, DV)").classes("text-xs font-semibold text-cyan-300")

            @ui.refreshable
            def _effects_list():
                if not effects_state:
                    ui.label("No structured modifiers (narrative / Markdown only).").classes("text-xs text-gray-500 italic")
                else:
                    for idx, ef in enumerate(effects_state):
                        with ui.row().classes("w-full items-center justify-between px-2 py-1 rounded bg-gray-800/80 text-xs"):
                            lbl = _EFFECT_KINDS.get(ef["kind"], ef["kind"])
                            tgt = f" → {ef['target']}" if ef.get("target") else ""
                            ui.label(f"{lbl}{tgt} (+{ef.get('value', 1)})").classes("text-gray-200")
                            ui.button(
                                icon="close",
                                on_click=lambda i=idx: (effects_state.pop(i), _effects_list.refresh()),
                            ).props("flat round dense size=xs").classes("text-red-400")

            _effects_list()

            with ui.row().classes("w-full items-end gap-2 mt-1"):
                ef_kind = ui.select(options=_EFFECT_KINDS, value="rr_skill", label="Effect").props("dense outlined dark").classes("flex-[2]")
                ef_target = ui.input("Target (Skill/Spec/Attr)", placeholder="e.g. Ranged Weapons or pistols").props("dense outlined dark").classes("flex-[2]")
                ef_val = ui.number("Value", value=1, min=1, max=3, step=1).props("dense outlined dark").classes("w-20")

                def _add_effect():
                    effects_state.append({
                        "kind": ef_kind.value,
                        "target": (ef_target.value or "").strip(),
                        "value": int(ef_val.value or 1),
                        "note": "",
                    })
                    ef_target.set_value("")
                    _effects_list.refresh()

                ui.button("Add Effect", icon="add", on_click=_add_effect).props("outline dense color=cyan")

            def _on_type_change(e):
                if not is_new:
                    return
                chosen = str(e.value or "")
                try:
                    t_enum = AmpType(chosen)
                    essence_in.set_value(DEFAULT_AMP_ESSENCE.get(t_enum, 0.0))
                except ValueError:
                    pass
                # Only overwrite ally defaults when picking Custom (library pick sets its own).
                if lib_select is None or lib_select.value == "Custom…":
                    _sync_ally_checkbox(chosen)
                # Seed inline Markdown template for Cyberdecks when body is empty.
                if not (body_in.value or "").strip():
                    tmpl = _read_amp_template(chosen)
                    if tmpl:
                        body_in.set_value(tmpl)

            type_in.on_value_change(_on_type_change)

            if lib_select is not None:
                def _on_lib_pick(_=None):
                    row = lib_map.get(lib_select.value)
                    if row is None:
                        _sync_ally_checkbox(str(type_in.value or ""))
                        return
                    info = extract_ability_stat_block(row)
                    name_in.set_value(row.name)
                    chosen_type = info["amp_type"] if info["amp_type"] in [t.value for t in AmpType] else AmpType.EQUIPMENT.value
                    type_in.set_value(chosen_type)
                    rating_in.set_value(int(info["rating"]))
                    essence_in.set_value(float(info["essence_cost"]))
                    body_in.set_value(info["summary"])
                    effects_state.clear()
                    for ef in info["effects"]:
                        if isinstance(ef, dict):
                            effects_state.append(ef)
                    _effects_list.refresh()
                    _sync_ally_checkbox(
                        chosen_type,
                        ally_type=info["ally_type"] or "",
                        stat_md=info["stat_block_md"] or "",
                    )

                lib_select.on_value_change(_on_lib_pick)

            async def _commit():
                nm = (name_in.value or "").strip()
                if not nm:
                    notify_error("Amp name is required.")
                    return

                linked_ally_id = existing.ally_id if existing else None
                if is_new and seed_ally_box is not None and seed_ally_box.visible and seed_ally_box.value:
                    ally_type = pending_ally["ally_type"] or "Vehicle"
                    ally_md = pending_ally["stat_block_md"] or (body_in.value or "")
                    async with service_session() as session:
                        created_ally = await create_ally(
                            session,
                            char_id,
                            AllyCreate(name=nm, ally_type=ally_type, body_md=ally_md),
                            user,
                        )
                    linked_ally_id = created_ally.id
                    reload_allies = state.get("reload_allies")
                    if callable(reload_allies):
                        await reload_allies()

                payload = {
                    "id": existing.id if existing else str(uuid.uuid4()),
                    "name": nm,
                    "amp_type": type_in.value or AmpType.EQUIPMENT.value,
                    "rating": int(rating_in.value or 0),
                    "essence_cost": float(essence_in.value or 0.0),
                    "effects": list(effects_state),
                    "body_md": body_in.value or "",
                    "ally_id": linked_ally_id,
                    "is_custom": True if not is_new else (lib_select is None or lib_select.value == "Custom…"),
                }
                amps = [a.model_dump() for a in state["cs"].shadow_amps]
                if is_new:
                    amps.append(payload)
                else:
                    amps[existing_idx] = payload
                await _save({"shadow_amps": amps})
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat").style("color:#94A3B8;")
                ui.button("Save", on_click=_commit).props("unelevated color=primary")
        dlg.open()

    @ui.refreshable
    def _section():
        vd = state["vd"]
        amps = vd.get("shadow_amps", [])
        active_filter = state["anarchy_amp_filter"]

        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
                ui.label("Shadow Amps").classes("text-lg font-bold text-white")
                with ui.row().classes("items-center gap-1 flex-wrap"):
                    for grp in _FILTER_GROUPS:
                        btn_props = "unelevated dense color=cyan-8" if active_filter == grp else "flat dense"
                        ui.button(
                            grp,
                            on_click=lambda g=grp: (state.__setitem__("anarchy_amp_filter", g), _section.refresh()),
                        ).props(btn_props).classes("text-xs")
                    ui.button("Add Amp", icon="add", on_click=lambda: _open_amp_editor(None)).props("unelevated dense color=primary").classes("ml-2")

            filtered = [a for a in amps if _matches_filter(a["amp_type"], active_filter)]
            if not filtered:
                ui.label("No Shadow Amps in this view. Click 'Add Amp' to pick from the catalog or add custom chrome/decks/vehicles.").classes("text-xs text-gray-500 italic")
                return

            for amp in filtered:
                amp_id = amp["id"]
                is_open = amp_id in state["anarchy_amps_expanded"]

                def _toggle(aid=amp_id):
                    if aid in state["anarchy_amps_expanded"]:
                        state["anarchy_amps_expanded"].discard(aid)
                    else:
                        state["anarchy_amps_expanded"].add(aid)
                    _section.refresh()

                with ui.card().classes("w-full bg-[#1a1d2e] border border-gray-800 p-2"):
                    with ui.row().classes("w-full items-center justify-between cursor-pointer").on("click", _toggle):
                        with ui.row().classes("items-center gap-2 flex-wrap"):
                            ui.icon("expand_more" if is_open else "chevron_right").classes("text-gray-400")
                            ui.label(amp["name"]).classes("text-sm font-bold text-white")
                            ui.badge(amp["amp_type"], color="cyan-9").classes("text-[11px]")
                            for ef in amp.get("effects", []):
                                label = ef.get("note") or f"{_EFFECT_KINDS.get(ef['kind'], ef['kind'])} {ef.get('target', '')}".strip()
                                ui.badge(label, color="emerald-9").classes("text-[10px]")
                        with ui.row().classes("items-center gap-2").on("click.stop", lambda: None):
                            if amp.get("ally_id"):
                                ui.button(
                                    "Stat Block",
                                    icon="open_in_new",
                                    on_click=lambda aid=amp["ally_id"]: state["open_ally"](aid),
                                ).props("flat dense size=sm").classes("text-cyan-300 text-xs").tooltip("Open full stat block in Allies & Stat Blocks")
                            if amp["essence_cost"]:
                                ui.badge(f"Ess -{amp['essence_display']}", color="red-9").classes("font-mono text-[11px]")
                            ui.badge(f"R{amp['rating']} ({amp['cost_nuyen']:,}¥)", color="amber-9").classes("font-mono text-[11px]")
                            ui.button(
                                icon="edit",
                                on_click=lambda i=amp["index"]: _open_amp_editor(i),
                            ).props("flat round dense size=sm").classes("text-gray-300")
                            ui.button(
                                icon="delete",
                                on_click=lambda i=amp["index"]: _delete_amp(i),
                            ).props("flat round dense size=sm").classes("text-red-400")

                    if is_open and (amp.get("body_md") or "").strip():
                        ui.separator().classes("my-2")
                        ui.markdown(amp["body_md"]).classes("w-full px-2 text-sm text-gray-200")

    _section()
    return _section
