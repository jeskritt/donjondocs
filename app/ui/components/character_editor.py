"""
AI Helper Docstring
Purpose: Shared NiceGUI modal for creating or editing a character's core identity
(name, optional ruleset/edition selector, classes + archetype + level list, ancestry/species, culture, background).
Interactions:
- `app.ui.pages.sheet_creator.py`: opens the modal in "create" mode (with edition selector for D&D 5e).
- `app.ui.pages.character_sheet.py`: opens the modal in "edit" mode from the top-bar edit button.
- `app.services.global_items_service.list_classes`: provides the class dropdown options.
"""

from nicegui import ui

from app.schemas.char_sheet_global import SheetStyle


def _ancestry_labels_for(style: SheetStyle) -> tuple[str, str]:
    """Return (primary, secondary) origin field labels for the given SheetStyle."""
    if style == SheetStyle.DND5E_2024:
        return ("Species", "Lineage / Subspecies")
    return ("Ancestry / Race", "Culture / Subrace")


async def open_character_editor(
    *,
    style: SheetStyle,
    available_classes: list[str],
    initial: dict | None = None,
    title: str = "New Character",
    confirm_label: str = "Create",
    vigor_class_names: set[str] | None = None,
    edition_options: list[tuple[str, SheetStyle]] | None = None,
    classes_by_style: dict[SheetStyle, list[str]] | None = None,
) -> dict | None:
    """Show a modal for editing character identity and return the form values on confirm.

    `vigor_class_names` are class names that grant a Vigor save (e.g. the UM5
    Magus). Selecting one auto-checks and locks the "Include Vigor" box, since
    the save flow force-enables Vigor for such classes.

    When `edition_options` is supplied (e.g. D&D 5e 2024 vs 2014 in create mode),
    renders a "Ruleset / Edition" selector at the top of the dialog that switches
    the active `SheetStyle`, updates origin labels, and swaps the class dropdown
    options using `classes_by_style`.

    Return value on confirm:
        {
            "style": SheetStyle,
            "name": str,
            "ancestry": str,
            "culture": str | None,
            "background": str,
            "classes": [
                {"name": str, "archetype": str | None, "level": int},
                ...
            ],
            "vigor_enabled": bool,   # UM5 only; always False for other styles
        }

    Returns None if the user cancels or closes the dialog.
    """
    initial = initial or {}
    vigor_casters = vigor_class_names or set()
    active_style = [style]

    def _options_for(st: SheetStyle) -> list[str]:
        base = (classes_by_style or {}).get(st, available_classes)
        return list(base) + ["Custom…"]

    options = _options_for(active_style[0])
    initial_classes = initial.get("classes") or [{"name": (options[0] if len(options) > 1 else "Fighter"), "archetype": None, "level": 1}]

    ancestry_label, culture_label = _ancestry_labels_for(active_style[0])

    dialog = ui.dialog().props("persistent")
    with dialog, ui.card().classes("w-[640px] max-w-full"):
        ui.label(title).classes("text-xl font-bold mb-2")

        # Optional ruleset/edition selector (used by the unified D&D 5e card to
        # pick between 2024 SRD 5.2 and 2014 SRD 5.1 without cluttering /sheet/new).
        edition_select = None
        if edition_options:
            edition_map = {st.value: lbl for lbl, st in edition_options}
            edition_select = ui.select(
                options=edition_map,
                value=active_style[0].value,
                label="Ruleset / Edition",
            ).classes("w-full mb-2").props("outlined dark")

        name_input = ui.input(label="Name", value=initial.get("name", "")).classes("w-full").props("outlined dark")

        with ui.row().classes("w-full gap-2 mt-2"):
            ancestry_input = ui.input(label=ancestry_label, value=initial.get("ancestry", "Human")).classes("flex-1").props("outlined dark")
            culture_input = ui.input(label=culture_label, value=initial.get("culture") or "").classes("flex-1").props("outlined dark")
        background_input = ui.input(label="Background", value=initial.get("background", "Peasant")).classes("w-full mt-2").props("outlined dark")

        # Ultramodern5 only: opt the character into the optional Vigor attribute
        # (7th ability score powering the DARK magic system). Hidden for other
        # styles so their editors stay unchanged.
        vigor_checkbox = None
        if style == SheetStyle.UM5:
            vigor_checkbox = ui.checkbox(
                "Include Vigor (Ultramodern5 magic attribute)",
                value=bool(initial.get("vigor_enabled", False)),
            ).classes("mt-2")

        ui.separator().classes("my-4")
        ui.label("Classes").classes("text-lg font-semibold")

        # Dynamic class list. Each row tracks its own widgets; the outer list holds them.
        class_rows: list[dict] = []
        rows_container = ui.column().classes("w-full gap-2")

        def _sync_vigor_lock():
            """Lock 'Include Vigor' on when a Vigor-caster class is chosen — the
            save flow force-enables Vigor for those, so reflect it in the UI."""
            if vigor_checkbox is None:
                return

            def _row_name(r):
                v = r["class_select"].value
                return (r["custom_name"].value or "").strip() if v == "Custom…" else v

            if any(_row_name(r) in vigor_casters for r in class_rows):
                vigor_checkbox.value = True
                vigor_checkbox.disable()
            else:
                vigor_checkbox.enable()

        def _add_row(entry: dict | None = None):
            cur_options = _options_for(active_style[0])
            entry = entry or {"name": cur_options[0] if cur_options else "Custom…", "archetype": None, "level": 1}
            with rows_container:
                with ui.row().classes("w-full items-end gap-2") as row:
                    class_select = ui.select(
                        cur_options,
                        value=entry["name"] if entry["name"] in cur_options else "Custom…",
                        label="Class",
                    ).classes("flex-[2]").props("outlined dark")
                    # Free-text fallback when Custom is picked (or when name not in list).
                    custom_name = ui.input(
                        label="Custom class name",
                        value=entry["name"] if entry["name"] not in cur_options else "",
                    ).classes("flex-[2]").props("outlined dark")
                    archetype_input = ui.input(
                        label="Archetype",
                        value=entry.get("archetype") or "",
                    ).classes("flex-[2]").props("outlined dark")
                    level_input = ui.number(
                        label="Level",
                        value=int(entry.get("level") or 1),
                        min=1,
                        max=20,
                    ).classes("w-24").props("outlined dark")

                    def _toggle_custom(e=None, cs=class_select, cn=custom_name):
                        cn.visible = (cs.value == "Custom…")
                    class_select.on("update:model-value", _toggle_custom)
                    class_select.on("update:model-value", lambda: _sync_vigor_lock())
                    custom_name.on("blur", lambda: _sync_vigor_lock())
                    _toggle_custom()

                    remove_btn = ui.button(icon="delete").props("flat round dense")

                    row_ref = {
                        "class_select": class_select,
                        "custom_name": custom_name,
                        "archetype_input": archetype_input,
                        "level_input": level_input,
                        "row": row,
                    }
                    class_rows.append(row_ref)

                    def _remove(_=None, target=row_ref):
                        if len(class_rows) <= 1:
                            return  # Always keep at least one row.
                        class_rows.remove(target)
                        target["row"].delete()
                        _sync_vigor_lock()
                    remove_btn.on("click", _remove)

        if edition_select is not None:
            def _on_edition_change(e):
                if not e.value:
                    return
                try:
                    new_style = SheetStyle(e.value)
                except ValueError:
                    return
                active_style[0] = new_style
                a_lbl, c_lbl = _ancestry_labels_for(new_style)
                ancestry_input.props(f'label="{a_lbl}"')
                culture_input.props(f'label="{c_lbl}"')
                ancestry_input.update()
                culture_input.update()
                new_opts = _options_for(new_style)
                for r in class_rows:
                    cur = r["class_select"].value
                    keep = cur if cur in new_opts else (new_opts[0] if new_opts else "Custom…")
                    r["class_select"].set_options(new_opts, value=keep)
                    r["custom_name"].visible = (keep == "Custom…")

            edition_select.on_value_change(_on_edition_change)

        for c in initial_classes:
            _add_row(c)
        _sync_vigor_lock()

        with ui.row().classes("w-full mt-2"):
            ui.button("+ Add Class", on_click=lambda: _add_row()).props("flat dense")

        ui.separator().classes("my-4")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=lambda: dialog.submit(None)).props("flat")
            ui.button(confirm_label, on_click=lambda: dialog.submit("ok")).props("unelevated color=primary")

    resolved = await dialog
    if resolved != "ok":
        return None

    # Collect values
    classes_out: list[dict] = []
    for r in class_rows:
        cls_val = r["class_select"].value
        if cls_val == "Custom…":
            name = (r["custom_name"].value or "").strip() or "Custom"
        else:
            name = cls_val or "Fighter"
        archetype = (r["archetype_input"].value or "").strip() or None
        try:
            level = int(r["level_input"].value or 1)
        except (TypeError, ValueError):
            level = 1
        if level < 1:
            level = 1
        classes_out.append({"name": name, "archetype": archetype, "level": level})

    return {
        "style": active_style[0],
        "name": (name_input.value or "").strip() or "Unnamed Adventurer",
        "ancestry": (ancestry_input.value or "").strip() or "Human",
        "culture": ((culture_input.value or "").strip() or None),
        "background": (background_input.value or "").strip() or "Peasant",
        "classes": classes_out,
        "vigor_enabled": bool(vigor_checkbox.value) if vigor_checkbox is not None else False,
    }
