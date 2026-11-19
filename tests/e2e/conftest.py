"""
AI Helper Docstring
Purpose: Pytest fixtures for the isolated Playwright browser E2E suite. Boots a
real `main.py` NiceGUI + FastAPI server against a throwaway SQLite DB migrated
via Alembic and seeded with a test user, so browser tests exercise the full
stack (AuthMiddleware, WebSockets, SQLite persistence, auto-ingest) without
touching the developer's local `donjondocs.db`.
Interactions:
- `main.py`: launched in a subprocess on a dynamically chosen localhost port.
- `alembic`: upgrades the temp DB from scratch before booting.
- `cli.py`: seeds the E2E user account.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Page, expect

REPO_ROOT = Path(__file__).resolve().parents[2]

E2E_USERNAME = "torak_tester"
E2E_EMAIL = "torak_e2e@example.com"
E2E_PASSWORD = "E2eTestPassword123!"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, proc: subprocess.Popen, log_file: Path, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            logs = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else ""
            raise RuntimeError(
                f"E2E server exited prematurely (code {proc.returncode}).\n"
                f"--- server.log ---\n{logs[-4000:]}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
        time.sleep(0.25)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    logs = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else ""
    raise RuntimeError(
        f"E2E server did not become ready at {url} within {timeout}s "
        f"(last error: {last_err}).\n--- server.log ---\n{logs[-4000:]}"
    )


@pytest.fixture(scope="session")
def e2e_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    """Run an isolated DonjonDocs server backed by a fresh temp SQLite DB."""
    work_dir = tmp_path_factory.mktemp("donjondocs_e2e")
    db_file = work_dir / "e2e.db"
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    # NiceGUI's ui.run() switches into its internal screen-test mode when
    # PYTEST_CURRENT_TEST is present, expecting NICEGUI_SCREEN_TEST_PORT.
    # Strip pytest's env var so the subprocess boots like a real server.
    env.pop("PYTEST_CURRENT_TEST", None)
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_file.as_posix()}",
            "SECRET_KEY": "e2e-test-secret-key-not-for-production-use",
            "STORAGE_SECRET": "e2e-test-storage-secret-not-for-production-use",
            "DEBUG": "true",
            "HSTS_ENABLED": "false",
            "ALLOWED_HOSTS": "127.0.0.1,localhost",
            "ALLOW_REGISTRATION": "true",
            "PORT": str(port),
            "PYTHONUNBUFFERED": "1",
        }
    )

    # 1. Run Alembic migrations from scratch.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    # 2. Seed a dedicated E2E user.
    subprocess.run(
        [
            sys.executable,
            "cli.py",
            "create-user",
            "--username",
            E2E_USERNAME,
            "--email",
            E2E_EMAIL,
            "--password",
            E2E_PASSWORD,
            "--role",
            "standard",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    # 3. Pre-ingest global reference CSVs with DEBUG=false (avoids verbose SQL
    # echo during bulk seeding).
    ingest_env = env.copy()
    ingest_env["DEBUG"] = "false"
    subprocess.run(
        [sys.executable, "-m", "app.cli.ingest", "data/"],
        cwd=str(REPO_ROOT),
        env=ingest_env,
        check=True,
        capture_output=True,
        text=True,
    )

    # 4. Launch main.py writing output to a file (not PIPE, which can deadlock
    # on Windows when SQLAlchemy DEBUG echo fills the 64 KiB pipe buffer).
    log_file = work_dir / "server.log"
    with log_file.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            _wait_for_server(f"{base_url}/login", proc, log_file)
            yield {
                "base_url": base_url,
                "username": E2E_USERNAME,
                "email": E2E_EMAIL,
                "password": E2E_PASSWORD,
            }
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


@pytest.fixture
def checked_page(page: Page) -> Iterator[Page]:
    """Playwright `page` that fails the test on any uncaught browser JS error."""
    page.set_viewport_size({"width": 1440, "height": 960})
    page.set_default_timeout(15_000)
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    yield page
    assert not page_errors, f"Uncaught browser JS errors: {page_errors}"


def sign_in(page: Page, server: dict[str, str], query: str = "") -> None:
    """Log into the app through the real `/login` form."""
    page.goto(f"{server['base_url']}/login{query}")
    expect(page.get_by_role("button", name="Sign In")).to_be_visible()
    page.get_by_label("Email").fill(server["email"])
    page.get_by_label("Password").fill(server["password"])
    page.get_by_role("button", name="Sign In").click()
    # Wait for the post-login navigation away from /login.
    expect(page).not_to_have_url(f"{server['base_url']}/login{query}")


@pytest.fixture(scope="session")
def e2e_auth_cookies(e2e_server: dict[str, str]) -> list[dict[str, object]]:
    """Log in once per session and return the browser cookie payload.

    Avoids tripping `/api/auth/login`'s 5/minute SlowAPI rate limit as the E2E
    suite grows, while keeping real rate limiting active on the E2E server.
    Interactive login/logout flows still test `/login` directly via `sign_in()`.
    """
    payload = json.dumps(
        {"email": e2e_server["email"], "password": e2e_server["password"]}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{e2e_server['base_url']}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        assert resp.status == 200
        cookie = SimpleCookie()
        for header_val in resp.headers.get_all("Set-Cookie") or []:
            cookie.load(header_val)
    assert "access_token" in cookie, "POST /api/auth/login did not set access_token cookie"
    return [
        {
            "name": "access_token",
            "value": cookie["access_token"].value,
            "url": e2e_server["base_url"],
            "httpOnly": True,
            "sameSite": "Lax",
        }
    ]


@pytest.fixture
def authed_page(
    checked_page: Page,
    e2e_server: dict[str, str],
    e2e_auth_cookies: list[dict[str, object]],
) -> Page:
    """Return a logged-in `checked_page` sitting on the dashboard."""
    checked_page.context.add_cookies(e2e_auth_cookies)
    checked_page.goto(f"{e2e_server['base_url']}/")
    expect(checked_page.get_by_text(f"Welcome back, {e2e_server['username']}")).to_be_visible()
    return checked_page
