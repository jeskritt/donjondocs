# User stories

End-to-end walkthroughs of how typical actions flow through the app. Each story names the files involved.

- [Create a new D&D 5e character](#create-a-new-dd-5e-character)
- [Long rest restores a character](#long-rest-restores-a-character)
- [Edit an attribute and watch dependents update](#edit-an-attribute-and-watch-dependents-update)
- [Annotate a skill with notes](#annotate-a-skill-with-notes)
- [Add a custom currency](#add-a-custom-currency)
- [Edit a user-added component](#edit-a-user-added-component)
- [Export a character](#export-a-character)
- [Import a character](#import-a-character)
- [Admin resets a forgotten password](#admin-resets-a-forgotten-password)
- [Re-ingest the global content library](#re-ingest-the-global-content-library)

## Create a new D&D 5e character

1. User navigates to `/sheet/new` (`app/ui/pages/sheet_creator.py`). Middleware allows it because the user is logged in.
2. User picks "Dungeons & Dragons 5e" → the creation modal (`app/ui/components/character_editor.py`) opens with class options sourced from `list_classes(session, SheetStyle.DND5E, owner_id=user.id)`.
3. User adds two class rows: Fighter 3, Wizard 2. Submits.
4. `create_character` (`app/services/character_service.py`) seeds each class's hit dice from `GlobalClass`, seeds save proficiencies and weapon/armor proficiencies from the primary (first) class only, seeds attribute scores from `GlobalAttribute`, seeds the full skill list from `GlobalSkill` (Shadowdark skipped), computes `total_level=5`, auto-derives `prof_bonus` from total level (not user-editable), and writes the JSON blob via `CharacterRecord(character_data=blank_data)`. The Skills card's "Add Skill" button is reserved for custom / DM-added entries.
5. Page redirects to `/character/<id>`. Top bar shows level 5 and the class summary `Fighter 3 / Wizard 2` (archetypes shown in parentheses when present, e.g. `Fighter 3 (Champion)`).

## Long rest restores a character

1. On the character sheet, user clicks the **Long Rest** button in the top bar.
2. Handler `_open_rest_dialog("long")` opens a confirmation dialog.
3. User confirms → `_apply_rest("long", {})` posts to the service.
4. `rest_character` (`app/services/character_service.py`) authorizes the user (owner or admin), then calls the pure helper `apply_rest(data, "long", options)`:
   - `hp_current = hp_max`, `hp_temp = 0`, `exhaustion = max(0, exhaustion-1)`.
   - Distributes `floor(total_level/2)` hit dice across classes by deficit.
   - Refills every magic resource (slots / per-level / Shadowdark / points).
   - Resets ability trackers whose `reset_on` is `short` or `long`.
   - Resets each magic resource's `extra_resource` tracker if its `reset_on` matches the rest type.
   - Resets `exertion_current` to `exertion_max` (A5e combat maneuvers; resets on both short and long rest).
5. The page re-renders all cards via the `refresh_fns` list — HP shows `8/8`, hit dice and slot indicators update.

## Edit an attribute and watch dependents update

1. User edits **STR** on the Abilities & Saves card and clicks Save.
2. `_save({"str_score": {...}})` runs `update_character`, then re-builds the view model, then calls `.refresh()` on every tracked `_section`.
3. Skills, Defenses, Magic spell attack/DC (when STR-based), and Actions all recompute their derived numbers without any per-card wiring.

## Annotate a skill with notes

1. On the character sheet, user clicks the **edit** icon on the Skills card.
2. Each skill row expands to include a `Notes` input (inline). User types a note on Perception — "Hears whispers in the wind."
3. User clicks **Save** → `_save_skills` posts the full list, each dict carrying `name / attribute / proficiency / misc / example_uses / notes`.
4. Display view re-renders; the note appears under the skill name in smaller, lighter italic text.
5. The card itself is capped at ~440px; overflow scrolls inside the card so the sheet layout stays compact. Shadowdark characters never see the card (no skill system).
6. `CharacterSkillSimple.notes` is optional (`str | None`); the builder (`build_skills_view` in `app/builders/base.py`) passes it through to `view_data['skills'][i]['notes']`.

## Add a custom currency

1. User opens **Equipment → Coins** tab.
2. Clicks **Add Currency** → enters code `EP` and amount `12`.
3. `_save({"equipment": {"money": {...EP: 12}}})` persists.
4. The Coins tab re-renders with the new currency tile, ± buttons, and delete control.
5. 5e characters start with `CP/SP/EP/GP/PP = 0`; Shadowdark starts with `GP = 0` (see `_default_money` in `character_service.py`).

## Edit a user-added component

Actions, abilities, magic resources, spells, and combat maneuvers all follow the same edit pattern.

1. User opens the relevant card or tab (e.g. Actions card, Abilities tab, Magic tab).
2. Clicks the **Edit** (pencil icon) button on the item they want to modify.
3. A dialog opens pre-populated with the item's current values — same fields as the Add dialog.
4. User changes fields and clicks **Save**.
5. The confirm handler replaces the item in the list by index (`updated[idx] = new.model_dump()`) and calls `_save()` with the full updated list.
6. The card/tab re-renders with the updated values.

## Export a character

1. User navigates to `/characters` (`app/ui/pages/characters.py`).
2. Clicks the **download** icon on a character row.
3. `handle_export` calls `export_character()` (`app/services/character_service.py`) which RBAC-checks ownership, then returns a versioned envelope: `{version, exported_at, name, style, character_data}`.
4. `ui.download()` triggers a browser download of `{name}.json`.
5. Alternatively, the REST endpoint `GET /api/characters/{id}/export` returns the same JSON with a `Content-Disposition: attachment` header.

## Import a character

1. User navigates to `/characters` and clicks the **Import** button (next to "New Sheet").
2. An upload dialog opens. User selects a `.json` file exported from DonjonDocs.
3. `_handle_upload` parses the JSON, validates the envelope structure and game system.
4. Calls `import_character()` (`app/services/character_service.py`) which validates `character_data` against the `Character` Pydantic schema, overrides `owner_id` with the current user, generates a new UUID, enforces the 25-character limit, and creates the `CharacterRecord`.
5. The table refreshes showing the newly imported character.

## Admin resets a forgotten password

CLI path:

```bash
python cli.py reset-password --email user@example.com --new-password "NewPass123!"
```

UI path: an admin signs in, navigates to `/admin/users` (gated by `current_user.role == ADMIN`), opens the user, and submits a new password through the user-edit form.

## Re-ingest the global content library

After updating the bundled CSVs in `data/`:

```bash
python -m app.cli.ingest data/
```

The ingest is idempotent — existing rows are upserted by `(name, source, owner_id IS NULL)` so re-running is safe. The startup auto-ingest only fires when global tables are empty; manually re-running is the way to refresh after CSV edits.
