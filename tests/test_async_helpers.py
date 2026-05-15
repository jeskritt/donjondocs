"""
Tests for app.ui.async_helpers.defer_load.

Validates the teardown-resilience contract that motivated the helper: the
deferred callback runs on a live client, but is a clean no-op (never raising)
when the client never connects, has gone away, or the callback itself hits the
NiceGUI 3.12 ``parent slot ... has been deleted`` RuntimeError.
"""

import types

import pytest

import app.ui.async_helpers as async_helpers
from app.ui.async_helpers import defer_load


class _FakeClient:
    def __init__(self, client_id: str = "c1", *, connect_error: Exception | None = None):
        self.id = client_id
        self._connect_error = connect_error

    async def connected(self, timeout=None):
        if self._connect_error is not None:
            raise self._connect_error


@pytest.fixture
def harness(monkeypatch):
    """Patch defer_load's NiceGUI seams so the deferred coroutine can be
    captured and awaited deterministically. Returns a builder that wires a
    client + instance registry and yields the captured coroutine."""
    captured: list = []

    def _fake_create(awaitable, *, name=None):
        captured.append(awaitable)

    monkeypatch.setattr(
        async_helpers, "background_tasks", types.SimpleNamespace(create=_fake_create)
    )

    def _build(client: _FakeClient, *, in_instances: bool):
        monkeypatch.setattr(
            async_helpers, "context", types.SimpleNamespace(client=client)
        )
        instances = {client.id: client} if in_instances else {}
        monkeypatch.setattr(
            async_helpers, "Client", types.SimpleNamespace(instances=instances)
        )
        return captured

    return _build


async def test_runs_sync_callback_on_live_client(harness):
    ran = []
    captured = harness(_FakeClient(), in_instances=True)
    defer_load(lambda: ran.append("sync"))
    await captured[0]
    assert ran == ["sync"]


async def test_runs_async_callback_on_live_client(harness):
    ran = []

    async def _load():
        ran.append("async")

    captured = harness(_FakeClient(), in_instances=True)
    defer_load(_load)
    await captured[0]
    assert ran == ["async"]


async def test_noop_when_client_never_connects(harness):
    ran = []
    client = _FakeClient(connect_error=RuntimeError("connection timed out"))
    captured = harness(client, in_instances=True)
    defer_load(lambda: ran.append("should-not-run"))
    await captured[0]  # must not raise
    assert ran == []


async def test_noop_when_client_gone_before_load(harness):
    ran = []
    captured = harness(_FakeClient(), in_instances=False)
    defer_load(lambda: ran.append("should-not-run"))
    await captured[0]
    assert ran == []


async def test_callback_runtimeerror_is_suppressed(harness):
    """A torn-down refreshable/slot surfaces as RuntimeError inside the
    callback; defer_load must swallow it (no error reaches the caller)."""

    def _boom():
        raise RuntimeError("The parent slot of the element has been deleted.")

    captured = harness(_FakeClient(), in_instances=True)
    defer_load(_boom)
    await captured[0]  # must not raise


async def test_delay_branch_still_runs(harness):
    ran = []
    captured = harness(_FakeClient(), in_instances=True)
    defer_load(lambda: ran.append("delayed"), delay=0.01)
    await captured[0]
    assert ran == ["delayed"]
