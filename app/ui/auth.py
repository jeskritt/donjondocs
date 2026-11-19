"""Page-side access to the DB-verified current user.

The AuthMiddleware populates `request.state.user` with a `UserContext`
on every protected page request. Page functions retrieve it through
`current_user_context()` instead of reaching into `app.storage.user`
and forging an ad-hoc user object.
"""

from urllib.parse import urlsplit

from nicegui import context

from app.user_context import UserContext


def sanitize_redirect_target(target: str | None) -> str:
    """Validate a post-login `redirect_to` query parameter to prevent open redirects.

    Allows only relative same-origin paths beginning with a single `/`. Rejects
    absolute URLs (`https://...`), protocol-relative URLs (`//evil.com`),
    backslash tricks (`/\\evil.com`), and control characters (`\\r`, `\\n`).
    Falls back to `"/"` on anything unsafe.
    """
    if not target or not isinstance(target, str):
        return "/"
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in target):
        return "/"
    if "\\" in target or not target.startswith("/") or target.startswith("//"):
        return "/"
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return "/"
    return target


def current_user_context() -> UserContext:
    """Return the DB-verified `UserContext` for the current request.

    Must be called inside a `@ui.page` handler whose URL is covered by
    `AuthMiddleware` (i.e. not in PUBLIC_PATHS / PUBLIC_PREFIXES). If
    the middleware didn't attach a context, that's a programming error
    in page routing, not a runtime auth decision.
    """
    request = context.client.request
    if request is None:
        raise RuntimeError(
            "current_user_context() called outside an HTTP request; "
            "the page may be executing in a context where the request "
            "is not available."
        )
    user = getattr(request.state, "user", None)
    if not isinstance(user, UserContext):
        raise RuntimeError(
            "No UserContext attached to request.state — is this page "
            "reachable without going through AuthMiddleware?"
        )
    return user
