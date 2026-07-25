"""Abilities & features sub-tab — used by the dispatcher in `features.py`.

Renders a per-source tab list of character abilities (class features,
feats, item powers, etc.) with optional use trackers, plus add/edit
dialogs.
"""

from nicegui import ui

from app.schemas.char_sheet_specific import (
    AbilityTracker,
    CharacterAbilityEntry,
    SubAbilityEntry,
)
from app.ui.components.sheet.helpers import _render_ability_tracker
from app.ui.theme import DIALOG_CARD_STYLE, notify_error


def _render_abilities_tab(state, cs, features, _save):
    if not features:
        ui.label("No abilities or features added yet.").classes('text-gray-500 italic text-sm py-2')

    # Which ability expansions are open. Bound into page `state` so they survive the
    # `_save` re-render — otherwise ticking a use tracker collapses the card on every
    # click. Keyed by `source:name` since ability names aren't enforced-unique.
    expanded = state.setdefault("abilities_expanded", set())

    sources = list(dict.fromkeys(f["source"] or "General" for f in features))
    if sources:
        if state.get("features_source_tab") not in sources:
            state["features_source_tab"] = sources[0]
        with ui.tabs().classes('w-full').bind_value(state, "features_source_tab") as tabs:
            tab_objs = {src: ui.tab(src) for src in sources}
        with ui.tab_panels(tabs, value=state["features_source_tab"]).classes('w-full').bind_value(state, "features_source_tab"):
            for src in sources:
                with ui.tab_panel(tab_objs[src]):
                    for feat in [f for f in features if (f["source"] or "General") == src]:
                        key = f"{src}:{feat['name']}"
                        exp = ui.expansion(feat["name"], icon='auto_fix_high',
                                           value=(key in expanded)).classes('w-full border border-gray-700 rounded mb-1')
                        exp.on_value_change(lambda e, k=key: expanded.add(k) if e.value else expanded.discard(k))
                        with exp:
                            if feat["description"]:
                                ui.label(feat["description"]).classes('text-gray-300 text-sm whitespace-pre-wrap')
                            for sub in feat.get("sub_abilities", []):
                                with ui.row().classes('gap-2 mt-1'):
                                    ui.label("▸").classes('text-indigo-400')
                                    with ui.column().classes('gap-0'):
                                        ui.label(sub["name"]).classes('font-bold text-gray-200 text-sm')
                                        if sub.get("description"):
                                            ui.label(sub["description"]).classes('text-gray-400 text-xs')

                            tracker = feat.get("tracker")
                            fname = feat["name"]
                            if tracker:
                                _render_ability_tracker(cs, fname, tracker, _save)

                            with ui.row().classes('gap-1 mt-2'):
                                ui.button("Edit", icon='edit', on_click=lambda n=fname: _open_edit_ability(cs, _save, n)).props('flat dense color=primary')

                                async def _remove(n=fname):
                                    updated = [a for a in cs.abilities if a.name != n]
                                    await _save({"abilities": [a.model_dump() for a in updated]})
                                ui.button("Remove", icon='delete', on_click=_remove).props('flat dense color=negative')

    def _open_add():
        _open_add_ability(cs, _save)

    ui.button("Add Ability / Feature", icon='add', on_click=_open_add).props('unelevated color=indigo').classes('mt-2')


def _open_add_ability(cs, _save):
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Add Ability / Feature").classes('text-lg font-bold mb-2 text-white')
        inp_name   = ui.input("Name").classes('w-full')
        inp_source = ui.select(["Class","Background","Heritage","Culture","Feat","Item","DM Gift","General"], label="Source", value="Class").classes('w-full')
        inp_desc   = ui.textarea("Description").classes('w-full').props('rows=3')
        ui.label("Sub-features (optional)").classes('text-sm text-gray-400 mt-2')
        sub_inputs = []
        sub_container = ui.column().classes('w-full gap-1')

        def _add_sub():
            with sub_container:
                with ui.row().classes('w-full gap-2'):
                    n = ui.input("Name").classes('flex-1').props('dense')
                    d = ui.input("Description").classes('flex-1').props('dense')
                    sub_inputs.append((n, d))

        ui.button("+ Sub-feature", on_click=_add_sub).props('flat dense').classes('text-indigo-400')

        track_box = ui.checkbox("Track uses").classes('mt-3')
        track_fields = ui.row().classes('w-full gap-2 items-center')
        with track_fields:
            inp_max   = ui.number("Max uses", value=1, min=1, step=1).classes('flex-1').props('dense')
            inp_reset = ui.select(["short", "long", "none"], label="Reset on", value="long").classes('flex-1').props('dense')
        track_fields.set_visibility(False)
        track_box.on_value_change(lambda e: track_fields.set_visibility(bool(e.value)))

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm():
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                tracker = None
                if track_box.value:
                    tmax = int(inp_max.value or 1)
                    tracker = AbilityTracker(
                        current=tmax, maximum=tmax,
                        reset_on=inp_reset.value or "long",
                    )
                entry = CharacterAbilityEntry(
                    name=name, source=inp_source.value or "General",
                    description=inp_desc.value.strip(),
                    sub_abilities=[SubAbilityEntry(name=n.value.strip(), description=d.value.strip()) for n, d in sub_inputs if n.value.strip()],
                    tracker=tracker,
                )
                updated = [a.model_dump() for a in cs.abilities] + [entry.model_dump()]
                await _save({"abilities": updated})
                dialog.close()

            ui.button("Add", on_click=_confirm).props('unelevated color=primary')
    dialog.open()


def _open_edit_ability(cs, _save, ability_name):
    ability_obj = next((a for a in cs.abilities if a.name == ability_name), None)
    if not ability_obj:
        return
    ability_idx = next(i for i, a in enumerate(cs.abilities) if a.name == ability_name)
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
        ui.label("Edit Ability / Feature").classes('text-lg font-bold mb-2 text-white')
        inp_name   = ui.input("Name", value=ability_obj.name).classes('w-full')
        inp_source = ui.select(["Class","Background","Heritage","Culture","Feat","Item","DM Gift","General"], label="Source", value=ability_obj.source or "General").classes('w-full')
        inp_desc   = ui.textarea("Description", value=ability_obj.description).classes('w-full').props('rows=3')
        ui.label("Sub-features (optional)").classes('text-sm text-gray-400 mt-2')
        sub_inputs = []
        sub_container = ui.column().classes('w-full gap-1')

        with sub_container:
            for sub in ability_obj.sub_abilities:
                with ui.row().classes('w-full gap-2'):
                    n = ui.input("Name", value=sub.name).classes('flex-1').props('dense')
                    d = ui.input("Description", value=sub.description).classes('flex-1').props('dense')
                    sub_inputs.append((n, d))

        def _add_sub():
            with sub_container:
                with ui.row().classes('w-full gap-2'):
                    n = ui.input("Name").classes('flex-1').props('dense')
                    d = ui.input("Description").classes('flex-1').props('dense')
                    sub_inputs.append((n, d))

        ui.button("+ Sub-feature", on_click=_add_sub).props('flat dense').classes('text-indigo-400')

        has_tracker = ability_obj.tracker is not None
        track_box = ui.checkbox("Track uses", value=has_tracker).classes('mt-3')
        track_fields = ui.row().classes('w-full gap-2 items-center')
        with track_fields:
            inp_max   = ui.number("Max uses", value=ability_obj.tracker.maximum if has_tracker else 1, min=1, step=1).classes('flex-1').props('dense')
            inp_reset = ui.select(["short", "long", "none"], label="Reset on", value=ability_obj.tracker.reset_on if has_tracker else "long").classes('flex-1').props('dense')
        track_fields.set_visibility(has_tracker)
        track_box.on_value_change(lambda e: track_fields.set_visibility(bool(e.value)))

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

            async def _confirm(idx=ability_idx):
                name = inp_name.value.strip()
                if not name:
                    notify_error("Name required"); return
                tracker = None
                if track_box.value:
                    tmax = int(inp_max.value or 1)
                    old_tracker = ability_obj.tracker
                    cur = old_tracker.current if old_tracker and old_tracker.maximum == tmax else tmax
                    tracker = AbilityTracker(
                        current=cur, maximum=tmax,
                        reset_on=inp_reset.value or "long",
                    )
                entry = CharacterAbilityEntry(
                    name=name, source=inp_source.value or "General",
                    description=inp_desc.value.strip(),
                    sub_abilities=[SubAbilityEntry(name=n.value.strip(), description=d.value.strip()) for n, d in sub_inputs if n.value.strip()],
                    tracker=tracker,
                )
                updated = [a.model_dump() for a in cs.abilities]
                updated[idx] = entry.model_dump()
                await _save({"abilities": updated})
                dialog.close()

            ui.button("Save", on_click=_confirm).props('unelevated color=primary')
    dialog.open()
