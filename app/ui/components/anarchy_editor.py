"""
AI Helper Docstring
Purpose: NiceGUI modal for creating or editing a Shadowrun: Anarchy 2.0 runner's core identity (Streetname, Metatype with live attribute caps/Edge preview, and 5 Keywords).
Interactions:
- `app.ui.pages.sheet_creator`: opens in Create mode when the user picks Shadowrun: Anarchy 2.0.
- `app.ui.components.sheet_anarchy.top_bar`: opens in Edit mode from the top-bar edit button.
"""

from __future__ import annotations

from nicegui import ui

from app.schemas.shadowrun_anarchy import METATYPE_RULES, Metatype

_KEYWORD_HINTS = (
    "Keyword 1 — Metatype / Social Status (e.g. Ork street kid)",
    "Keyword 2 — Origins / Home (e.g. Seattle / Redmond)",
    "Keyword 3 — Role / Occupation (e.g. Combat decker, Street samurai)",
    "Keyword 4 — Lifestyle (e.g. Low Lifestyle, Middle Lifestyle)",
    "Keyword 5 — Secondary / Open (e.g. Former Lone Star, Smuggler)",
)


async def open_anarchy_character_editor(
    *,
    initial: dict | None = None,
    title: str = "New Shadowrun: Anarchy 2.0 Runner",
    confirm_label: str = "Create",
) -> dict | None:
    """Show the Shadowrun: Anarchy 2.0 identity modal and return form values on confirm."""
    initial = initial or {}
    init_meta = str(initial.get("metatype") or Metatype.HUMAN.value)
    init_kw = list(initial.get("keywords") or ["", "", "", "", ""])
    while len(init_kw) < 5:
        init_kw.append("")

    dialog = ui.dialog().props("persistent")
    with dialog, ui.card().classes("w-[640px] max-w-full"):
        ui.label(title).classes("text-xl font-bold mb-2 text-white")

        name_input = ui.input(
            label="Streetname",
            value=initial.get("name", ""),
        ).classes("w-full").props("outlined dark")

        meta_options = [m.value for m in Metatype]
        meta_select = ui.select(
            options=meta_options,
            value=init_meta if init_meta in meta_options else Metatype.HUMAN.value,
            label="Metatype",
        ).classes("w-full mt-2").props("outlined dark")

        meta_summary = ui.label("").classes("text-xs text-cyan-300 mt-1")

        def _refresh_meta_summary(_=None):
            try:
                m = Metatype(meta_select.value)
            except ValueError:
                m = Metatype.HUMAN
            info = METATYPE_RULES[m]
            caps = info["caps"]
            caps_str = " · ".join(f"{k} max {v}" for k, v in caps.items())
            meta_summary.set_text(
                f"Starting Edge: {info['edge_base']}  |  Racial Quality: {info['racial_quality']}  |  {caps_str}"
            )

        meta_select.on_value_change(_refresh_meta_summary)
        _refresh_meta_summary()

        ui.separator().classes("my-3")
        ui.label("Keywords (5)").classes("text-sm font-semibold text-gray-200")
        ui.label("Keywords define background and double as Knowledge Skills.").classes("text-xs text-gray-400 mb-1")

        kw_inputs = [
            ui.input(label=_KEYWORD_HINTS[i], value=init_kw[i]).classes("w-full").props("dense outlined dark")
            for i in range(5)
        ]

        ui.separator().classes("my-3")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=lambda: dialog.submit(None)).props("flat").style("color:#94A3B8;")
            ui.button(confirm_label, on_click=lambda: dialog.submit("ok")).props("unelevated color=primary")

    resolved = await dialog
    if resolved != "ok":
        return None

    chosen_meta = meta_select.value or Metatype.HUMAN.value
    keywords = [(inp.value or "").strip() for inp in kw_inputs]
    if not keywords[0]:
        keywords[0] = chosen_meta

    return {
        "name": (name_input.value or "").strip() or "Unnamed Runner",
        "metatype": chosen_meta,
        "keywords": keywords,
    }
