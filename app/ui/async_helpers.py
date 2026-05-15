"""UI async lifecycle helpers.

AI Helper Docstring
-------------------
**Why this module exists:** several pages/cards need to kick off an async load
*after* the element tree is built so the page paints immediately. The obvious
NiceGUI idiom — ``ui.timer(0, fn, once=True)`` — is fragile under NiceGUI
3.12+: a slot-bound one-shot timer resolves ``Element.parent_slot`` inside
``Timer._run_once`` *before* its own cancellation/deleted checks, and 3.12
hardened ``parent_slot`` to *raise* ``RuntimeError('The parent slot of the
element has been deleted.')`` when the slot weakref is dead (older versions
returned ``None``). So if the client disconnects/reconnects (WebSocket
reconnect, tab backgrounding, navigation) while the one-shot is still pending,
the timer task throws into the background-task exception handler and spams the
server log. The throw happens inside NiceGUI's own task, so a ``try/except`` in
the callback cannot catch it.

:func:`defer_load` replaces that idiom with a ``background_tasks``-driven
deferral that never touches a slot context, waits for the client to actually
connect, and no-ops cleanly once the client is gone. This is the project's
canonical deferred-load primitive — see ``docs/nicegui.md``.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from nicegui import background_tasks, context
from nicegui.client import Client


def defer_load(callback: Callable[[], Any], *, delay: float = 0.0) -> None:
    """Run ``callback`` once, after the current container is built, off the
    page-paint path, in a way that survives client teardown.

    Call this *during* page/element construction (so the current client can be
    captured). ``callback`` may be sync or async. If the client disconnects
    before the load runs — or is torn down mid-load — this no-ops instead of
    raising the NiceGUI 3.12 ``parent slot ... has been deleted`` error. Use
    this everywhere the old ``ui.timer(0, fn, once=True)`` deferred-load idiom
    was used.

    :param callback: zero-arg sync or async function performing the load
    :param delay: optional seconds to wait after connect before loading
    """
    client = context.client  # captured at build time → the right client

    async def _runner() -> None:
        # Wait for the websocket to be live before mutating UI state; bail
        # quietly if it never connects (navigated away, timed out).
        try:
            await client.connected()
        except Exception:
            return
        if delay:
            await asyncio.sleep(delay)
        # Client (and thus the element tree) may be gone by now.
        if client.id not in Client.instances:
            return
        # A refreshable/slot the callback targets can still vanish in the
        # window above; that surfaces as RuntimeError — treat as a no-op.
        with suppress(RuntimeError):
            result = callback()
            if inspect.isawaitable(result):
                await result

    background_tasks.create(
        _runner(), name=f'defer_load:{getattr(callback, "__name__", "load")}'
    )
