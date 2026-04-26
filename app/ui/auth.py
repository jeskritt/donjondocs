"""Page-side access to the DB-verified current user.

The AuthMiddleware populates `request.state.user` with a `UserContext`
on every protected page request. Page functions retrieve it through
`current_user_context()` instead of reaching into `app.storage.user`
and forging an ad-hoc user object.
"""

from nicegui import context

from app.user_context import UserContext


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
