"""
AI Helper Docstring
Purpose: Define the authoritative clean-venv test run. `nox` builds a throwaway
Python 3.14 virtualenv, installs the PINNED lockfiles, and runs pytest — so every
run also proves requirements.txt / requirements-dev.txt install cleanly on the
production Python (Render runs 3.14). CI invokes this same session.
Interactions:
- `requirements.txt` / `requirements-dev.txt`: the pinned inputs installed here.
- `.github/workflows/tests.yml`: runs `nox`, sharing this exact environment.
"""

import nox

# Bare `nox` runs the clean-venv test suite.
nox.options.sessions = ["tests"]


@nox.session(python="3.14")
def tests(session: nox.Session) -> None:
    """Install the pinned lockfiles into a fresh venv and run the test suite.

    A broken or incomplete pin fails here (in the fresh install) rather than only
    surfacing on a Render deploy. Extra args pass through to pytest, e.g.
    `nox -- tests/test_security.py -k migration`.
    """
    session.install("-r", "requirements.txt", "-r", "requirements-dev.txt")
    session.run("pytest", "tests/", "-v", *session.posargs)


@nox.session(python="3.14")
def e2e(session: nox.Session) -> None:
    """Install app + E2E browser deps into a separate venv and run Playwright tests.

    Opt-in (`nox -s e2e`) so the default unit/integration run stays fast.
    """
    session.install(
        "-r", "requirements.txt",
        "-r", "requirements-dev.txt",
        "-r", "requirements-e2e.txt",
    )
    session.run("playwright", "install", "chromium")
    session.run("pytest", "tests/e2e/", "-v", *session.posargs)
