"""New Sheet Selection Page — /sheet/new"""

from nicegui import ui

from app.services.session import service_session
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.services.character_service import create_character, CharacterServiceError
from app.services.global_items_service import list_classes
from app.ui.auth import current_user_context
from app.ui.theme import apply_global_styles, notify_error, notify_success
from app.ui.components.header import build_header
from app.ui.components.sidebar import build_sidebar
from app.ui.components.character_editor import open_character_editor
from app.ui.components.anarchy_editor import open_anarchy_character_editor
from app.rule_systems import SystemFamily, system_family_for


@ui.page("/sheet/new")
async def sheet_creator_page():
    """Select a game system and initialize a new character."""
    user = current_user_context()

    ui.dark_mode(True)
    apply_global_styles()
    ui.page_title("New Character — DonjonDocs")

    build_header()
    build_sidebar()

    with ui.column().classes("page-content items-center pt-10"):
        ui.label("Select Game System").classes("text-3xl font-bold text-white mb-2")
        ui.label("Choose the ruleset for your new character sheet.").classes("text-gray-400 mb-8")

        with ui.row().classes("gap-6 justify-center flex-wrap w-full max-w-5xl"):

            # Cards share width and a fixed height with `flex-nowrap` so a
            # taller title/description can never wrap the Select button into a
            # second column outside the card. `flex-1` on the description pins
            # every Select button cleanly to the bottom edge.
            def system_card(title: str, description: str, style: SheetStyle, icon: str, color: str):
                with ui.card().classes(
                    "w-64 h-80 flex flex-col flex-nowrap justify-between cursor-pointer hover:scale-105 transition-transform duration-200"
                ).style(
                    f"background: #1E1E2E; border-top: 4px solid {color};"
                ).on('click', lambda s=style: do_create(s)):
                    ui.icon(icon, size="3xl").classes("w-full text-center mt-2").style(f"color: {color};")
                    ui.label(title).classes("text-xl font-bold text-white w-full text-center mt-2 leading-tight")
                    ui.label(description).classes("text-xs text-gray-400 text-center mt-2 mb-3 flex-1")
                    ui.button("Select").props("unelevated outline").classes("w-full").style(f"color: {color};")

            system_card(
                "Dungeons & Dragons 5e",
                "2024 (SRD 5.2) or classic 2014 (SRD 5.1) core rules. Standard abilities, skills, and magic.",
                SheetStyle.DND5E,
                "auto_awesome",
                "#EF4444",
            )
            system_card(
                "Level Up: Advanced 5e",
                "A deeper, more tactical ruleset avoiding alignments and enhancing combat maneuvers.",
                SheetStyle.A5E,
                "account_tree",
                "#F59E0B",
            )
            system_card(
                "Shadowdark RPG",
                "Old-school renaissance (OSR). Minimalist attributes, torches, and swift combat.",
                SheetStyle.SHADOWDARK,
                "nights_stay",
                "#A855F7",
            )
            system_card(
                "Ultramodern5",
                "Sci-fi/modern expansion of 5e. Modern classes, dollar-priced gear, optional Vigor magic.",
                SheetStyle.UM5,
                "rocket_launch",
                "#22D3EE",
            )
            system_card(
                "Voidrunner",
                "Sci-fi expansion of Level Up: A5e. Psionic classes, credits, and futuristic gear atop A5e's Strife & combat maneuvers.",
                SheetStyle.VOIDRUNNER,
                "satellite_alt",
                "#34D399",
            )
            system_card(
                "Shadowrun: Anarchy 2.0",
                "Narrative cyberpunk-fantasy d6 dice pools. Metatypes, Shadow Amps, Essence, and Condition Monitors.",
                SheetStyle.SHADOWRUN_ANARCHY_2,
                "memory",
                "#EC4899",
            )

    async def do_create(style: SheetStyle):
        if system_family_for(style) == SystemFamily.SHADOWRUN_ANARCHY_2:
            form = await open_anarchy_character_editor(
                title="New Shadowrun: Anarchy 2.0 Runner",
                confirm_label="Create",
            )
            if form is None:
                return
            async with service_session() as session:
                try:
                    new_char = await create_character(
                        session,
                        form["name"],
                        style,
                        user,
                        metatype=form["metatype"],
                        keywords=form["keywords"],
                    )
                    notify_success(f"Created {form['name']}!")
                    ui.navigate.to(f"/character/{new_char.id}")
                except CharacterServiceError as e:
                    notify_error(e.message)
                except Exception as e:
                    notify_error(f"Failed to create character: {str(e)}")
            return

        edition_options: list[tuple[str, SheetStyle]] | None = None
        classes_by_style: dict[SheetStyle, list[str]] | None = None
        dialog_style = style
        dialog_title = f"New {style.value.upper()} Character"

        if style == SheetStyle.DND5E:
            edition_options = [
                ("2024 Rules (SRD 5.2)", SheetStyle.DND5E_2024),
                ("2014 Rules (SRD 5.1)", SheetStyle.DND5E),
            ]
            dialog_style = SheetStyle.DND5E_2024
            dialog_title = "New Dungeons & Dragons 5e Character"
            async with service_session() as session:
                rows_2024 = await list_classes(session, SheetStyle.DND5E_2024, owner_id=user.id)
                rows_2014 = await list_classes(session, SheetStyle.DND5E, owner_id=user.id)
            classes_by_style = {
                SheetStyle.DND5E_2024: [c.name for c in rows_2024],
                SheetStyle.DND5E: [c.name for c in rows_2014],
            }
            class_rows = rows_2024
        else:
            async with service_session() as session:
                class_rows = await list_classes(session, style, owner_id=user.id)

        class_names = [c.name for c in class_rows]
        from app.services.character_seeding import _parse_saving_throws
        vigor_class_names = {c.name for c in class_rows if "VIG" in _parse_saving_throws(c.saving_throws)}

        form = await open_character_editor(
            style=dialog_style,
            available_classes=class_names,
            title=dialog_title,
            confirm_label="Create",
            vigor_class_names=vigor_class_names,
            edition_options=edition_options,
            classes_by_style=classes_by_style,
        )
        if form is None:
            return

        chosen_style = form.get("style", dialog_style)
        async with service_session() as session:
            try:
                entries = [CharacterClassEntry(**c) for c in form["classes"]]
                new_char = await create_character(
                    session,
                    form["name"],
                    chosen_style,
                    user,
                    classes=entries,
                    ancestry=form["ancestry"],
                    culture=form["culture"],
                    background=form["background"],
                    vigor_enabled=form.get("vigor_enabled", False),
                )
                notify_success(f"Created {form['name']}!")
                ui.navigate.to(f"/character/{new_char.id}")
            except CharacterServiceError as e:
                notify_error(e.message)
            except Exception as e:
                notify_error(f"Failed to create character: {str(e)}")
