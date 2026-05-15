# DonjonDocs Documentation

Reference docs for DonjonDocs — a FastAPI + NiceGUI character-sheet web app.

Audience: AI assistants and humans onboarding to the codebase.

## Index

| Doc | Topic |
| --- | --- |
| [architecture.md](architecture.md) | Layer stack, request lifecycle, character-sheet rendering pipeline |
| [database.md](database.md) | Tables, FK relationships, ER diagram |
| [deployment.md](deployment.md) | Running locally, env vars, prod deployment sketch |
| [rbac.md](rbac.md) | UserRole enum, route protection, ownership rules |
| [dependencies.md](dependencies.md) | Component interaction graph |
| [nicegui.md](nicegui.md) | NiceGUI conventions, sanctioned exceptions, deferred divergences |
| [user_stories.md](user_stories.md) | Example end-to-end flows |
| [operations.md](operations.md) | Backup & restore CLI |

## Conventions

- Mermaid diagrams are fenced as ` ```mermaid ` so GitHub renders them inline.
- Each doc is self-contained with a TOC at the top.
- Code references use `path:line` form (e.g. `app/services/character_service.py:156`).
