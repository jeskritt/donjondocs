"""Features-card dispatcher: switches between abilities, magic, and
combat-maneuvers sub-tabs.

Each sub-system lives in its own module
(`features_abilities.py`, `features_magic.py`, `features_maneuvers.py`)
so this file stays a thin orchestrator. The combat-maneuvers tab is
hidden when the active rule system doesn't expose it (Shadowdark, etc.).
"""

from nicegui import ui

from app.ui.components.sheet.features_abilities import _render_abilities_tab
from app.ui.components.sheet.features_magic import _render_magic_tab
from app.ui.components.sheet.features_maneuvers import _render_maneuvers_tab


def _render_features(state, char_id, user, _save):
    @ui.refreshable
    def _section():
        cs = state["cs"]
        vd = state["vd"]
        features = vd.get("features", [])
        magic = vd.get("magic", {"resources": [], "spells": []})
        maneuvers_data = vd.get("combat_maneuvers")
        maneuvers = maneuvers_data["maneuvers"] if maneuvers_data else None

        with ui.card().classes('w-full flex-[2] min-w-[500px]'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Abilities, Magic & Features").classes('text-xl font-bold font-serif')
            ui.separator()

            with ui.tabs().classes('w-full').bind_value(state, "features_tab") as outer_tabs:
                tab_abilities = ui.tab("Abilities")
                tab_magic = ui.tab("Magic")
                tab_maneuvers = ui.tab("Combat Maneuvers") if maneuvers_data is not None else None

            with ui.tab_panels(outer_tabs, value=state["features_tab"]).classes('w-full').bind_value(state, "features_tab").style('max-height: 400px; overflow-y: auto;'):

                with ui.tab_panel(tab_abilities):
                    _render_abilities_tab(state, cs, features, _save)

                with ui.tab_panel(tab_magic):
                    _render_magic_tab(state, cs, magic, _save, user=user)

                if tab_maneuvers is not None:
                    with ui.tab_panel(tab_maneuvers):
                        _render_maneuvers_tab(state, cs, maneuvers_data, maneuvers, _save, user=user)

    _section()
    return _section
