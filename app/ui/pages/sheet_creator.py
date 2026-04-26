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

        with ui.row().classes("gap-6 justify-center w-full max-w-4xl"):

            def system_card(title: str, description: str, style: SheetStyle, icon: str, color: str):
                with ui.card().classes("w-64 cursor-pointer hover:scale-105 transition-transform duration-200").style(
                    f"background: #1E1E2E; border-top: 4px solid {color};"
                ).on('click', lambda s=style: do_create(s)):
                    ui.icon(icon, size="3xl").classes("w-full text-center mt-4").style(f"color: {color};")
                    ui.label(title).classes("text-xl font-bold text-white w-full text-center mt-4")
                    ui.label(description).classes("text-xs text-gray-400 text-center mt-2 mb-4 h-16")
                    ui.button("Select").props("unelevated outline").classes("w-full").style(f"color: {color};")

            system_card(
                "Dungeons & Dragons 5e",
                "The classic 2014 core ruleset. Standard abilities, skills, and magic.",
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

    async def do_create(style: SheetStyle):
        async with service_session() as session:
            class_rows = await list_classes(session, style, owner_id=user.id)
        class_names = [c.name for c in class_rows]

        form = await open_character_editor(
            style=style,
            available_classes=class_names,
            title=f"New {style.value.upper()} Character",
            confirm_label="Create",
        )
        if form is None:
            return

        async with service_session() as session:
            try:
                entries = [CharacterClassEntry(**c) for c in form["classes"]]
                new_char = await create_character(
                    session,
                    form["name"],
                    style,
                    user,
                    classes=entries,
                    ancestry=form["ancestry"],
                    culture=form["culture"],
                    background=form["background"],
                )
                notify_success(f"Created {form['name']}!")
                ui.navigate.to(f"/character/{new_char.id}")
            except CharacterServiceError as e:
                notify_error(e.message)
            except Exception as e:
                notify_error(f"Failed to create character: {str(e)}")
