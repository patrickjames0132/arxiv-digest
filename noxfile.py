"""Quality gate for arXiv Atlas — run every check with ``uv run nox``.

Four sessions, all run by default: ``precommit`` (pre-commit hooks, incl. ruff),
``mypy`` (type checks), ``tests`` (pytest), and ``security`` (a Trivy filesystem
scan). Sessions reuse the active uv environment (``venv_backend="none"``) rather
than building their own, so ``uv run nox`` needs no per-session installs — the
tools come from the ``dev`` dependency group.

Trivy is an external binary (not a Python package); the ``security`` session
skips itself cleanly when ``trivy`` isn't on PATH, so ``uv run nox`` stays green
on machines that don't have it installed.
"""

from __future__ import annotations

import shutil

import nox

# Reuse the uv-managed env; don't spin up a venv per session.
nox.options.default_venv_backend = "none"
# Bare `uv run nox` runs all four gates, in this order.
nox.options.sessions = ["precommit", "mypy", "tests", "security"]


@nox.session
def precommit(session: nox.Session) -> None:
    """Run every pre-commit hook (file hygiene + ruff lint) over the whole tree."""
    session.run("pre-commit", "run", "--all-files", external=True)


@nox.session
def mypy(session: nox.Session) -> None:
    """Type-check the backend package (config in ``pyproject.toml``)."""
    session.run("mypy")


@nox.session
def tests(session: nox.Session) -> None:
    """Run the unit-test suite (``test/``), passing through any extra args."""
    session.run("pytest", *session.posargs)


@nox.session
def security(session: nox.Session) -> None:
    """Scan the repo for known vulnerabilities with Trivy (skipped if absent)."""
    if shutil.which("trivy") is None:
        session.skip("trivy not on PATH — install it to enable the security scan")
    session.run("trivy", "fs", "--scanners", "vuln,secret", ".", external=True)
