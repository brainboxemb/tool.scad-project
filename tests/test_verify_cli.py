"""Public verification-domain CLI contract for the v0.10 boundary.

Checks:
The public ``verify`` command runs verification without invoking the normal Build
domain or materializing normal ``bld/`` output. The old public ``functional-verify``
command is absent at the intentional v0.10 breaking boundary.

Testing approach:
Tests run the real argparse dispatcher against a temporary ``ProjectContext`` while
monkeypatching validation and execution dependencies. Any normal ``build_project`` call
fails the test immediately, and argparse is exercised directly to prove the removed
command is no longer accepted.
"""

from pathlib import Path
import sys

import pytest

import scad_project.cli as cli
from scad_project.config import ProjectContext


def _context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={"project": {"name": "demo"}},
    )


def test_verify_runs_verification_without_normal_build(tmp_path: Path, monkeypatch):
    ctx = _context(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(cli, "load_context", lambda project: ctx)
    monkeypatch.setattr(cli, "validate_config", lambda context: [])
    monkeypatch.setattr(cli, "validate_build_engine_config", lambda context: [])
    monkeypatch.setattr(cli, "validate_release_config", lambda context: [])
    monkeypatch.setattr(cli, "validate_externals_config", lambda context: [])
    monkeypatch.setattr(cli, "check_externals", lambda context: [])
    monkeypatch.setattr(cli, "lint_docs", lambda context: [])
    monkeypatch.setattr(cli, "lint_design", lambda context: ([], []))
    monkeypatch.setattr(
        cli,
        "build_project",
        lambda context: pytest.fail("verify must not invoke the normal build domain"),
    )
    monkeypatch.setattr(
        cli,
        "run_functional_verification",
        lambda context: calls.append("verification"),
    )
    monkeypatch.setattr(sys, "argv", ["scad-project", "verify"])

    cli.main()

    assert calls == ["verification"]
    assert not (tmp_path / "bld").exists()


def test_functional_verify_is_not_a_public_command(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["scad-project", "functional-verify"])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
