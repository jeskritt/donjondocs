# Component dependencies

- [Module graph](#module-graph)
- [Narrative](#narrative)

## Module graph

```mermaid
flowchart TD
  subgraph entry
    main[main.py]
  end

  subgraph api[app/api]
    auth_r[auth_routes]
    user_r[user_routes]
    char_r[character_routes]
    deps[deps.py]
  end

  subgraph ui[app/ui]
    mw[middleware.AuthMiddleware]
    pages[pages/*]
    cmps[components/header,sidebar]
    sheet[components/sheet/*]
  end

  subgraph services[app/services]
    auth_s[AuthService]
    user_s[UserService]
    char_s[character_service]
    global_s[global_items_service]
  end

  subgraph schemas[app/schemas]
    cs_g[char_sheet_global]
    cs_s[char_sheet_specific]
  end

  subgraph builders[app/builders]
    base_b[base.BaseSheetBuilder]
    dnd5e_b[dnd5e]
    a5e_b[a5e]
    sd_b[shadowdark]
  end

  subgraph models[app/models]
    user_m[User]
    char_m[CharacterRecord]
    global_m[char_sheet GlobalX]
  end

  main --> mw
  main --> pages
  main --> auth_r
  main --> user_r
  main --> char_r

  auth_r --> deps
  user_r --> deps
  char_r --> deps
  deps --> auth_s

  auth_r --> auth_s
  user_r --> user_s
  char_r --> char_s

  pages --> char_s
  pages --> global_s
  pages --> builders
  pages --> cmps
  pages --> sheet
  sheet --> global_s

  auth_s --> user_m
  user_s --> user_m
  char_s --> char_m
  char_s --> cs_s
  global_s --> global_m

  builders --> cs_s
  cs_s --> cs_g
```

## Narrative

- **Builders depend only on schemas.** They never touch the DB. A builder converts a `Character` schema into a plain dict view-model the UI cards consume. This makes them trivial to unit-test in isolation.
- **Services depend on models + schemas, not on UI or API.** They own all DB writes and authorization. Both UI pages and API routes funnel through services — never query the ORM directly.
- **API depends on services + Pydantic request bodies.** Each route is thin: parse, call a service, translate exceptions to HTTP.
- **UI depends on services + builders.** The character sheet orchestrator (`app/ui/pages/character_sheet.py`) delegates rendering to card components in `app/ui/components/sheet/`. Each card's `_section` refresh handle is collected and re-rendered on save (the "refresh-all" pattern). The single write path is `_save(updates)` in `character_sheet.py`.
- **Models depend on the database layer only.** They never import schemas or services.
- **Middleware depends on `nicegui.app`** for storage and lives outside the service stack. It is the only auth guard for UI pages; API routes use the JWT dep in `app/api/deps.py`.
- **NiceGUI is pinned `>=3.12,<4`** (`requirements.txt`). Bumped from 3.10 for the 3.12 security fix (unauthenticated DoS on dynamic-resource/ESM routes) plus stability fixes that touch our code paths: silent window reloads on WebSocket reconnect (long-lived character sheet), a `ValidationElement.validate()` KeyError (we use `validation=` on login/register/profile), a Windows `PermissionError` during `app.storage.user` cleanup, and unbounded streaming-cookie memory growth. No API breakage applied (audited). Conventions: `docs/nicegui.md`.

## Dependency risks (tracked, not yet actionable)

Most of `requirements*.txt` uses version *floors* (only deliberate caps:
`nicegui>=3.12,<4`, `bcrypt<5`), so installs already resolve to current
releases — there is no "bump" that removes the standing `DeprecationWarning`s.
Two of those warnings are upstream Python-3.14 deprecations correctly silenced
in `pytest.ini`; do **not** treat them as fixable by upgrading:

- **`slowapi` is dormant — forward-incompatible.** Latest is `0.1.9`
  (Feb 2024); the project shows no 2025/2026 activity. `slowapi/extension.py`
  calls `asyncio.iscoroutinefunction`, which Python **3.14 deprecates and 3.16
  removes**. On 3.16 the rate limiter would *break*, not just warn, and no
  newer slowapi exists. **Action when 3.16 nears:** vendor a one-line patch
  (`inspect.iscoroutinefunction`), swap the limiter, or hold Python `<3.16`.
- **`pytest-asyncio` event-loop-policy warning is upstream, not stale.**
  `1.3.0` (current) still calls `asyncio.get/set_event_loop_policy` for its
  `event_loop_policy` fixture; Python 3.14 deprecated those (removal 3.16). No
  released version is silent yet — the `pytest.ini` filter stays until upstream
  ships a 3.14-clean release.
- **`passlib 1.7.4` (2020, unmaintained)** under the `bcrypt<5` cap with
  bcrypt 3.2.2. Works today; the cap exists because newer bcrypt trips
  passlib's `bcrypt.__about__` probe. A future auth-hashing migration
  (passlib → bcrypt-direct or argon2) is the real fix; keep the cap until then.

The httpx per-request `cookies=` deprecation that *was* visible in the test
run came from our own tests, not a dependency — fixed by standardising on the
suite-wide `client.cookies = auth_cookies(user)` pattern (see
`tests/test_creature_routes.py`).
