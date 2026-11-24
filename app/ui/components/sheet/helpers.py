from nicegui import ui


_PROF_ICONS = {
    0: ("○", "text-gray-500"),
    1: ("½", "text-yellow-400"),
    2: ("●", "text-blue-400"),
    3: ("◉", "text-purple-400"),
}


def _fmt_bonus(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


def render_pm_adjuster(
    on_delta,
    *,
    minus_tooltip: str | None = None,
    plus_tooltip: str | None = None,
):
    """Render minus/plus buttons that call on_delta(±1).

    on_delta is an async callable; clamping is the caller's job.
    """
    btn_m = ui.button(icon='remove', on_click=lambda: on_delta(-1)).props('flat round dense size=sm')
    btn_p = ui.button(icon='add',    on_click=lambda: on_delta(1)).props('flat round dense size=sm')
    if minus_tooltip:
        btn_m.tooltip(minus_tooltip)
    if plus_tooltip:
        btn_p.tooltip(plus_tooltip)


def render_plain_markdown(text) -> None:
    """Render a markdown description WITHOUT the PHB parchment typography.

    Spell/maneuver/equipment descriptions should read like the rest of the dark
    UI regardless of the sheet's PHB-style toggle, so this deliberately never
    attaches the vendored `.phb` class (unlike notes.py/allies.py, which gate on
    it). No-op for empty text so callers can pass an optional field directly.
    """
    if not text:
        return
    ui.markdown(str(text)).classes('w-full text-sm text-gray-200 whitespace-normal')


def render_detail_pairs(pairs) -> None:
    """Render a wrap-row of `Label: value` chips, skipping empty values.

    The shared "label: value" block for the expanded (extended) view on the
    spell, maneuver, and equipment list rows. `pairs` is an iterable of
    (label, value); a value of None/""/"—" is dropped so absent fields don't
    clutter the block. Callers pre-format non-string values (e.g. bool → Yes/No).
    """
    with ui.row().classes('w-full flex-wrap gap-x-4 gap-y-1'):
        for label, value in pairs:
            if value in (None, "", "—"):
                continue
            with ui.row().classes('items-baseline gap-1 no-wrap'):
                ui.label(f"{label}:").classes('text-gray-500 text-xs')
                ui.label(str(value)).classes('text-gray-300 text-xs')


def toggle_element_display(el) -> None:
    """Flip an element's inline `display` between none/block.

    Backs the DOM-only expand/collapse of the description row on the spell,
    maneuver, and equipment lists — no server round-trip, no card re-render.
    """
    visible = el.style.get('display', 'none') != 'none'
    el.style('display: none' if visible else 'display: block')


def make_toggle_handler(is_editing, display_col, edit_col, edit_btn):
    def _toggle():
        is_editing[0] = not is_editing[0]
        display_col.set_visibility(not is_editing[0])
        edit_col.set_visibility(is_editing[0])
        edit_btn._props['icon'] = 'close' if is_editing[0] else 'edit'
        edit_btn.update()
    return _toggle


def _render_ability_tracker(cs, ability_name: str, tracker: dict, _save):
    current = tracker.get("current", 0)
    maximum = tracker.get("maximum", 1)
    reset_on = tracker.get("reset_on", "long")

    async def _persist(new_current: int):
        new_current = max(0, min(maximum, int(new_current)))
        updated = []
        for a in cs.abilities:
            d = a.model_dump()
            if a.name == ability_name and d.get("tracker"):
                d["tracker"]["current"] = new_current
            updated.append(d)
        await _save({"abilities": updated})

    with ui.row().classes('w-full items-center gap-2 mt-2'):
        ui.label(f"Uses ({current}/{maximum}, resets {reset_on})").classes('text-gray-400 text-xs')

    if maximum < 5:
        with ui.row().classes('gap-1 mt-1'):
            spent = maximum - current
            for i in range(maximum):
                is_spent = i < spent
                def _mk_handler():
                    async def _h(e):
                        new_spent = spent + (1 if e.value else -1)
                        await _persist(maximum - new_spent)
                    return _h
                ui.checkbox(value=is_spent, on_change=_mk_handler()).props('dense')
    elif maximum < 10:
        async def _slider_change(e):
            await _persist(int(e.value))
        ui.slider(min=0, max=maximum, step=1, value=current, on_change=_slider_change).props('dense label').classes('w-full')
    else:
        async def _num_change(e):
            await _persist(int(e.value or 0))
        ui.number(label="Current", value=current, min=0, max=maximum, step=1, on_change=_num_change).props('dense').classes('w-32')


def _render_slot_checkboxes(cs, resource_name: str, cur_list: list[int],
                            max_list: list[int], magic_type: str, _save):
    from app.schemas.char_sheet_global import MagicType

    async def _toggle(level_idx: int, slot_idx: int, now_spent: bool):
        updated = []
        for mr in cs.magic_resources:
            d = mr.model_dump()
            if mr.name == resource_name and isinstance(d.get("current"), list):
                cur = list(d["current"])
                mx = d["maximum"][level_idx] if level_idx < len(d.get("maximum") or []) else 0
                cur_at = cur[level_idx] if level_idx < len(cur) else 0
                spent = max(0, mx - cur_at)
                spent = spent + 1 if now_spent else max(0, spent - 1)
                spent = min(spent, mx)
                while len(cur) <= level_idx:
                    cur.append(0)
                cur[level_idx] = mx - spent
                d["current"] = cur
            updated.append(d)
        await _save({"magic_resources": updated})

    is_perlevel = magic_type == MagicType.PERLEVEL.value

    for i, mx in enumerate(max_list):
        if mx <= 0:
            continue
        cur_at = cur_list[i] if i < len(cur_list) else 0
        spent = max(0, mx - cur_at)
        with ui.row().classes('items-center gap-1 mt-1'):
            if is_perlevel:
                ui.label(f"L{i + 1}").classes('text-gray-400 text-xs w-8 text-center')
            for slot_idx in range(mx):
                is_spent = slot_idx < spent

                def _mk_handler(li=i, si=slot_idx):
                    async def _h(e):
                        await _toggle(li, si, bool(e.value))
                    return _h

                ui.checkbox(value=is_spent, on_change=_mk_handler()).props('dense')
