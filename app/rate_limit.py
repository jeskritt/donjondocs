"""Shared SlowAPI Limiter instance and proxy-aware client IP resolver.

Lives in its own module so router files can import the same instance
that `main.py` registers on the FastAPI app, without creating a
circular import back through `main`.
"""

from starlette.requests import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def get_client_ip(request: Request) -> str:
    """Return the rate-limiting key IP for `request`.

    When `TRUST_PROXY_HEADERS` is enabled (e.g. behind Render's TLS edge),
    takes the rightmost non-empty entry of `X-Forwarded-For` — the hop
    appended by the trusted reverse proxy — so clients cannot spoof earlier
    entries while distinct end-users still get independent rate-limit buckets.
    Otherwise ignores `X-Forwarded-For` and uses the direct peer address.
    """
    if get_settings().TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        hops = [part.strip() for part in forwarded_for.split(",") if part.strip()]
        if hops:
            return hops[-1]
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)
