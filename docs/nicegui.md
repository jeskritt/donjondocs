# NiceGUI conventions

Distilled from NiceGUI's official LLM reference. **Canonical source:**
<https://nicegui.io/llms.txt> (a.k.a. `nicegui/llms.md` upstream) — read that for
the full API surface. This doc keeps only the rules that bite in *this* codebase
plus the places we deliberately diverge, so the guidance matches reality.

- [Core rules](#core-rules)
- [Storage scopes](#storage-scopes)
- [Repo-specific patterns](#repo-specific-patterns)
- [Sanctioned exceptions](#sanctioned-exceptions)
- [Known divergences (deferred)](#known-divergences-deferred)

## Core rules

- **Python-first.** Use the `ui.*` API, `.classes()` (Tailwind/Quasar utilities),
  `.props()` (Quasar props), and bindings before raw CSS/JS. `ui.run_javascript()`
  is for things Python genuinely cannot do (see exceptions below) — never for
  styling, visibility, or content.
- **No virtual DOM.** Deleting an element destroys and recreates its Vue
  component, losing focus/scroll/animation state. Update in place
  (`.set_text()`, `.set_value()`, bindings) or wrap the volatile section in
  `@ui.refreshable`.
- **`@ui.page` runs once per page load**, not per state change. Drive updates
  via `@ui.refreshable`, bindings, or direct element mutation — never by
  re-running the page function.
- **Module-level state is process-wide**, shared across every connected user.
  Per-user state belongs in `app.storage.user`; request-scoped state stays
  local to the `@ui.page` function or in the page `state` dict.
- **One shared async event loop.** Blocking it freezes the whole app. All I/O is
  async; offload blocking I/O or CPU work via `await run.io_bound(...)` /
  `await run.cpu_bound(...)` (from `nicegui import run`, so NiceGUI manages pool
  lifecycle and shutdown); use `nicegui.background_tasks.create()` (not bare
  `asyncio.create_task()`) for fire-and-forget work so the task keeps a reference
  and routes exceptions.

## Storage scopes

| Scope | Lifetime | Audience | Used here for |
| --- | --- | --- | --- |
| local var in `@ui.page` | until reload | one session | per-render working state |
| page `state` dict | until reload | one session | active tab/scroll that must survive `_save` |
| `app.storage.client` | lost on reload | one connection | — |
| `app.storage.tab` | survives reload | one browser tab | — |
| `app.storage.user` | until cookie expires | per user | `phb_style`, auth session (`authenticated`) |
| `app.storage.general` | persistent on disk | all users | — |
| module-level var | server restart | **all users** | constants only — never mutable per-user state |

## Repo-specific patterns

- **The "refresh-all" save path.** `@ui.refreshable` card handles are collected
  via `_track()` into two trigger-split lists in
  `app/ui/pages/character_sheet.py`: `data_refresh_fns` (character_data cards,
  iterated by `_save`/`_apply_rest`) and `style_refresh_fns` (those plus the
  Allies/Notes panels, iterated by the PHB `_toggle_phb`). Don't add ad-hoc
  refresh code — go through `_save`. Allies/Notes own their own tables, read no
  character_data, and write via their services — they're registered
  `_track(..., data=False)` so a data save never rebuilds them. See `CLAUDE.md`
  → "The character sheet pipeline".
- **Deferred async load idiom — use `defer_load`.** To load data after the page
  builds without blocking the skeleton, call
  `app/ui/async_helpers.py::defer_load(callback, *, delay=0.0)` during element
  construction. Used in `app/ui/pages/creatures.py` and
  `app/ui/components/sheet/{allies,notes,equipment,description}.py`. **Do not
  use the raw `ui.timer(0, fn, once=True)` pattern for this** — under NiceGUI
  3.12+ a slot-bound one-shot timer resolves `Element.parent_slot` (which 3.12
  hardened to *raise* `RuntimeError('The parent slot of the element has been
  deleted.')`) before its own cancel/deleted checks, so a client
  disconnect/reconnect (WebSocket reconnect, tab backgrounding, navigation)
  while the timer is pending spams the server log with that traceback. The
  throw is inside NiceGUI's own task, so a `try/except` in the callback cannot
  catch it. `defer_load` instead drives the load via `background_tasks.create()`
  + a client-connected/alive guard, so teardown is a clean no-op (not data
  loss — the deferred content still loads on a normal connect).
- **Scoped third-party CSS.** Vendored stylesheets are *not* assumed to be
  scoped. The homebrewery PHB CSS is run through
  `app/static/vendor/homebrewery/scope_phb_css.py` and only the `.phb`-scoped
  derivative is served. Workflow: `app/static/vendor/homebrewery/README.md`.
  Always sample vendored content before claiming it is safe to load globally
  (CLAUDE.md "verify before asserting").

## Sanctioned exceptions

These look like anti-patterns but are intentional — do not "fix" them:

- **`ui.run_javascript()` for auth.** `app/ui/pages/{login,register,profile}.py`
  use `fetch()` via `run_javascript` so the *browser* sets/sends the HttpOnly
  auth cookie. Python cannot read or set HttpOnly cookies, so the browser must
  make these requests. This is the correct approach for our cookie-auth model,
  not a Python-first violation.
- **`ui.add_head_html(...)` in `app/ui/theme.py`** injects font preconnect/`<link>`
  tags and the scoped PHB stylesheet link — link/preconnect injection, not CSS
  styling. Global CSS itself goes through `ui.add_css(...)`.

## Known divergences (deferred)

Recorded so they aren't rediscovered cold. Deferred per YAGNI — not in scope of
the 3.12 upgrade:

- `.style('display: none' | 'display: block')` toggles in
  `app/ui/components/sheet/features_maneuvers.py` and `features_magic.py` could
  become `bind_visibility_from(...)` for proper reactivity.
- ~70 hardcoded-hex `.style('color: #...')` calls (e.g.
  `app/ui/components/header.py`) could move to theme classes / a Tailwind
  palette instead of inline CSS.
- `make_sortable()` / `ui.keep_alive` (added in 3.11) are available but unused —
  adopt only when a concrete need arises.
