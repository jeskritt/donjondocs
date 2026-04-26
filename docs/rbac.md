# RBAC

- [Roles](#roles)
- [Authentication](#authentication)
- [Authorization rules](#authorization-rules)
- [Custom global content](#custom-global-content)

## Roles

Defined in `app/models/user.py` as `UserRole`:

| Role | Capabilities |
| --- | --- |
| `admin` | Full access. Read/write any character; manage all users (`/admin/users`) |
| `premium` | Standard rights + reserved for future quota expansion |
| `standard` | Own characters only. Hard cap of 25 characters per `create_character` |

## Authentication

Two parallel mechanisms — both backed by the same `users` table:

1. **NiceGUI session** — `app.storage.user["authenticated"]` is set after a successful login. `app/ui/middleware.py:AuthMiddleware` redirects unauthenticated requests for any non-public path to `/login?redirect_to=...`.
2. **JWT cookie** — `/api/auth/login` returns an HttpOnly `access_token` cookie. `app/api/deps.py:get_current_user` decodes the JWT and loads the `User`. Used by every `/api/*` route.

Public allow-list (in middleware): `/login`, `/register`, plus the prefixes `/_nicegui`, `/api/`, `/_static`. Adding a new public route requires explicitly editing this list.

## Authorization rules

All authorization lives in services, not routes. The pattern is:

```python
char = await get_character(session, character_id, current_user)
# get_character raises CharacterServiceError if:
#  - the character doesn't exist
#  - current_user is not the owner AND not admin
```

Routes translate `CharacterServiceError` to HTTP status: 404 if the message contains "not found", 403 otherwise (see `app/api/character_routes.py:38`).

Matrix:

| Actor | Own character | Other user's character | Notes |
| --- | --- | --- | --- |
| owner | full CRUD | — | — |
| other standard/premium | — | 403 | — |
| admin | full CRUD | full CRUD | Can also reset user passwords via `cli.py reset-password` or `/admin/users` |
| unauthenticated | redirect to `/login` (UI) or 401 (API) | same | — |

User management routes (`/admin/users/*`) check `current_user.role == UserRole.ADMIN`; non-admins get 403.

## Custom global content

`global_class`, `global_skill`, `global_weapon`, `global_armor`, `global_item`, `global_attribute`:

- `owner_id IS NULL` → seeded from `data/`, visible to all users.
- `owner_id = <user.id>` → user-defined custom entry, visible only to that user (and admins).

The `list_*` helpers in `app/services/global_items_service.py` filter by `(owner_id IS NULL OR owner_id = :user_id)` so user-scoping is automatic at the query layer.
