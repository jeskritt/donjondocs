from nicegui import ui

from app.ui.auth import current_user_context
from app.ui.theme import DIALOG_CARD_STYLE, apply_global_styles, notify_success
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar
from app.builders import get_builder
from app.schemas.char_sheet_specific import Character
from app.services.session import service_session
from app.services.character_service import get_character, update_character, rest_character, CharacterServiceError
from app.services.global_items_service import list_classes
from app.ui.components.character_editor import open_character_editor

from app.ui.components.sheet.abilities import _render_abilities
from app.ui.components.sheet.actions import _render_actions
from app.ui.components.sheet.allies import _render_allies
from app.ui.components.sheet.notes import _render_notes
from app.ui.components.sheet.skills import _render_skills
from app.ui.components.sheet.hp import _render_hp
from app.ui.components.sheet.defenses import _render_defenses
from app.ui.components.sheet.proficiencies import _render_proficiencies
from app.ui.components.sheet.description import _render_description
from app.ui.components.sheet.features import _render_features
from app.ui.components.sheet.equipment import _render_equipment


# Tab labels are constants so the panel-name lookup never silently desyncs
# from the tab declarations. Order here is the order the tabs render.
PAGE_CHARACTER = "Character"
PAGE_ALLIES = "Allies & Stat Blocks"
PAGE_NOTES = "Notes"


@ui.page("/character/{char_id}")
async def character_sheet_page(char_id: str):
    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("Character Sheet")

    build_header()
    build_sidebar()

    user = current_user_context()

    try:
        async with service_session() as session:
            char_record = await get_character(session, char_id, user)
            char_schema = Character(**char_record.character_data)
            builder = get_builder(char_schema)
            view_data = builder.build()
    except CharacterServiceError as e:
        ui.label(e.message).classes("text-red-500 font-bold p-8 text-xl")
        return
    except Exception as e:
        ui.label("Error loading character.").classes("text-red-500 font-bold p-8 text-xl")
        print(f"Error parsing character {char_id}: {e}")
        return

    state = {
        "vd": view_data,
        "cs": char_schema,
        "features_tab": "Abilities",
        "features_source_tab": None,
        "equipment_tab": "Weapons",
        # Active page tab. Survives `_save` re-renders the same way the
        # features/equipment subtabs do.
        "active_page": PAGE_CHARACTER,
    }

    refresh_fns: list = []

    async def _save(updates: dict):
        async with service_session() as session:
            rec = await update_character(session, char_id, updates, user)
        new_schema = Character(**rec.character_data)
        state["cs"] = new_schema
        state["vd"] = get_builder(new_schema).build()
        for fn in refresh_fns:
            try:
                fn.refresh()
            except Exception:
                pass
        notify_success("Saved")

    async def _apply_rest(kind: str, options: dict):
        async with service_session() as session:
            rec = await rest_character(session, char_id, kind, options, user)
        new_schema = Character(**rec.character_data)
        state["cs"] = new_schema
        state["vd"] = get_builder(new_schema).build()
        for fn in refresh_fns:
            try:
                fn.refresh()
            except Exception:
                pass
        notify_success(f"{kind.title()} rest complete")

    def _open_rest_dialog(kind: str):
        cs = state["cs"]
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-md').style(DIALOG_CARD_STYLE):
            ui.label(f"{kind.title()} Rest").classes('text-lg font-bold mb-2 text-white')

            hd_inputs: dict = {}
            regain_slots = [False]

            if kind == "short":
                ui.label("Spend hit dice to recover HP").classes('text-sm text-gray-400')
                for ce in cs.classes:
                    if not ce.hit_dice:
                        continue
                    avail = ce.hit_dice_current if ce.hit_dice_current is not None else 0
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.label(f"{ce.name} ({ce.hit_dice})").classes('w-28 text-gray-300 text-sm')
                        ui.label(f"{avail} left").classes('text-xs text-gray-500')
                        hd_inputs[ce.name] = ui.number(label="Spend", value=0, min=0, max=avail, step=1).props('dense').classes('w-24')

                if any(r.magic_type.value == "Slots" for r in cs.magic_resources if r.magic_type):
                    chk = ui.checkbox("Regain Warlock-style spell slots").classes('mt-2')
                    chk.on_value_change(lambda e: regain_slots.__setitem__(0, bool(e.value)))
            else:
                ui.label("HP restored to max; half hit dice recovered; spell slots refilled.").classes('text-sm text-gray-400')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button("Cancel", on_click=dialog.close).props('flat').style('color:#94A3B8;')

                async def _confirm():
                    if kind == "short":
                        options = {
                            "hit_dice_spent": {name: int(inp.value or 0) for name, inp in hd_inputs.items()},
                            "regain_slots": regain_slots[0],
                        }
                    else:
                        options = {}
                    await _apply_rest(kind, options)
                    dialog.close()

                ui.button("Confirm", on_click=_confirm).props('unelevated color=primary')
        dialog.open()

    # -----------------------------------------------------------------------
    # Sticky Top Bar
    # -----------------------------------------------------------------------
    async def _edit_identity():
        cs = state["cs"]
        async with service_session() as session:
            class_rows = await list_classes(session, cs.style, owner_id=user.id)
        class_names = [c.name for c in class_rows]
        initial = {
            "name": cs.name,
            "ancestry": cs.race.ancestry,
            "culture": cs.race.culture,
            "background": cs.background,
            "classes": [
                {"name": ce.name, "archetype": ce.archetype, "level": ce.level}
                for ce in cs.classes
            ],
        }
        form = await open_character_editor(
            style=cs.style,
            available_classes=class_names,
            initial=initial,
            title="Edit Character",
            confirm_label="Save",
        )
        if form is None:
            return
        from app.schemas.char_sheet_specific import CharacterClassEntry
        from app.services.character_seeding import (
            _seed_classes_from_db, _aggregate_saves, _aggregate_proficiencies,
        )
        entries = [CharacterClassEntry(**c) for c in form["classes"]]
        async with service_session() as session:
            seeded = await _seed_classes_from_db(session, cs.style, user.id, entries)
        prof = _aggregate_proficiencies(seeded)
        current_prof = cs.proficiency.model_dump()
        current_prof["weapon"] = prof["weapon"]
        current_prof["armor"] = prof["armor"]

        saves = _aggregate_saves(seeded)

        await _save({
            "name": form["name"],
            "race": {
                "ancestry": form["ancestry"],
                "culture": form["culture"],
                "lineage": cs.race.lineage,
            },
            "background": form["background"],
            "classes": [c.model_dump() for c in seeded],
            "character_class": " / ".join(f"{c.name} {c.level}" for c in seeded) if len(seeded) > 1 else seeded[0].name,
            "level": sum(c.level for c in seeded),
            "proficiency": current_prof,
            "saving_throws": saves,
        })

    @ui.refreshable
    def _top_bar_section():
        top = state["vd"].get('top_bar', {})
        with ui.row().classes('w-full sticky top-[60px] z-40 p-2 shadow-md bg-opacity-90 border-b border-gray-700').style(
            'background-color: #1e1e2f; margin-top: -16px; margin-left: -16px; margin-right: -16px; padding: 1rem; width: calc(100% + 32px);'
        ):
            with ui.row().classes('w-full flex-wrap items-center justify-between gap-4 px-4'):
                with ui.column().classes('gap-0'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(top.get('name', '')).classes('text-3xl font-bold text-white')
                        ui.button(icon='edit', on_click=_edit_identity).props('flat round dense').classes('text-gray-400')
                    class_level = f"Lvl {top.get('level', 1)} {top.get('character_class', '')}"
                    ui.label(f"{top.get('race', '')} • {class_level}").classes('text-sm text-gray-400')

                chips = [('HP', None), ('AC', 'ac'), ('INIT', 'initiative'), ('SPEED', 'speed')]
                if state["vd"].get('style_flags', {}).get('show_prof_bonus', True):
                    chips.append(('PROF', 'prof_bonus'))
                with ui.row().classes('gap-6'):
                    for label, key in chips:
                        with ui.column().classes('items-center gap-0'):
                            ui.label(label).classes('text-xs text-gray-400')
                            if label == 'HP':
                                ui.label(f"{top.get('hp_current', 0)}/{top.get('hp_max', 0)}").classes('text-2xl font-bold text-white')
                            else:
                                ui.label(str(top.get(key, ''))).classes('text-2xl font-bold text-white')

                with ui.row().classes('gap-2'):
                    for rest in top.get('rest_options', []):
                        kind = "short" if "Short" in rest else "long"
                        ui.button(rest, icon='hotel',
                                  on_click=lambda _, k=kind: _open_rest_dialog(k)
                                  ).props('flat dense').classes('text-gray-300')

    _top_bar_section()
    refresh_fns.append(_top_bar_section)

    def _track(section):
        if section is not None:
            refresh_fns.append(section)

    # -----------------------------------------------------------------------
    # Page Tabs (Character / Allies / Notes)
    # -----------------------------------------------------------------------
    # Mounting Quasar's q-tabs sticky just below the existing top_bar
    # (which sits at top-[60px]). Tab content swaps via tab_panels — one URL,
    # no router. State["active_page"] mirrors the tab so a top-level _save
    # rerender doesn't snap users back to the Character tab.
    with ui.tabs(value=state["active_page"]).classes("w-full sticky top-[140px] z-30 bg-[#1e1e2f] border-b border-gray-700") as page_tabs:
        ui.tab(PAGE_CHARACTER)
        ui.tab(PAGE_ALLIES)
        ui.tab(PAGE_NOTES)
    page_tabs.bind_value(state, "active_page")

    with ui.tab_panels(page_tabs, value=state["active_page"]).bind_value(state, "active_page").classes("w-full bg-transparent"):
        # -------------------------------------------------------------------
        # Character page (the existing card grid)
        # -------------------------------------------------------------------
        with ui.tab_panel(PAGE_CHARACTER):
            with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):

                with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                    _track(_render_abilities(state, char_id, user, _save))
                    _track(_render_actions(state, char_id, user, _save))
                    _track(_render_skills(state, char_id, user, _save))

                with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                    _track(_render_hp(state, char_id, user, _save))
                    _track(_render_defenses(state, char_id, user, _save))
                    _track(_render_proficiencies(state, char_id, user, _save))

                with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                    _track(_render_description(state, char_id, user, _save))
                    _track(_render_features(state, char_id, user, _save))

                with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                    _track(_render_equipment(state, char_id, user, _save))

        # -------------------------------------------------------------------
        # Allies & Stat Blocks
        # -------------------------------------------------------------------
        with ui.tab_panel(PAGE_ALLIES):
            with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
                _track(_render_allies(state, char_id, user))

        # -------------------------------------------------------------------
        # Notes
        # -------------------------------------------------------------------
        with ui.tab_panel(PAGE_NOTES):
            with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
                _track(_render_notes(state, char_id, user))
