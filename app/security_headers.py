"""HTTP security headers middleware.

Closes the headers portion of security audit finding #5: missing CSP,
HSTS, X-Frame-Options, etc. Stateful CSRF tokens are out of scope for
this middleware — see the audit follow-up roadmap for that work.

The CSP policy is intentionally loose around `script-src` and
`style-src` because NiceGUI ships inlined Vue templates and
TailwindCSS-generated styles that legitimately need
`'unsafe-inline'` / `'unsafe-eval'`. Tightening that is a separate
project (would require a NiceGUI nonce-passthrough or a build step).
The other directives still cut off most XSS payload classes.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Built once at import time so we don't pay string-join cost per request.
_CSP_POLICY = "; ".join((
    "default-src 'self'",
    # NiceGUI inlines Vue render functions and uses `eval` for compiled
    # templates; Tailwind ships a runtime that uses inline styles.
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "img-src 'self' data: blob:",
    "font-src 'self' https://fonts.gstatic.com data:",
    # Websocket connection for NiceGUI's reactive UI plus same-origin XHR.
    "connect-src 'self' ws: wss:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
))

_PERMISSIONS_POLICY = ", ".join((
    "geolocation=()",
    "microphone=()",
    "camera=()",
    "payment=()",
    "usb=()",
))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive HTTP headers to every response."""

    def __init__(self, app, *, hsts_enabled: bool = False) -> None:
        super().__init__(app)
        self._hsts_enabled = hsts_enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        headers = response.headers
        # setdefault so endpoint-specific overrides (rare) win.
        headers.setdefault("Content-Security-Policy", _CSP_POLICY)
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        if self._hsts_enabled:
            # 6 months, include subdomains. Only emitted when the deploy
            # serves HTTPS (config flag); dev on plain http://localhost
            # would otherwise sticky-cache HSTS in the browser.
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=15552000; includeSubDomains",
            )
        return response
