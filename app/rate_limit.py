"""Shared SlowAPI Limiter instance.

Lives in its own module so router files can import the same instance
that `main.py` registers on the FastAPI app, without creating a
circular import back through `main`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)
