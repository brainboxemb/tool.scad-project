"""Project verification commands

Checks:
Verification commands in `project.yml` must be explicit argument lists such as
`["python3", "check.py"]`. A single shell command string is rejected so command
execution does not depend on shell parsing, quoting or command injection behavior.

Testing approach:
The tests create minimal project configurations containing either the supported
argument-list form or the rejected shell-string form, then call the real verification-
command parser and inspect the returned commands or error.
"""

from pathlib import Path
import pytest

from scad_project.config import ProjectContext
from scad_project.verification import verification_commands


def test_verification_commands_are_argv_lists(tmp_path: Path):
    ctx = ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={
            "verification": {
                "commands": [["bash", "scripts/check.sh"], ["python3", "probe.py"]]
            }
        },
    )
    assert verification_commands(ctx) == [
        ["bash", "scripts/check.sh"],
        ["python3", "probe.py"],
    ]


def test_verification_rejects_shell_string(tmp_path: Path):
    ctx = ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={"verification": {"commands": ["bash scripts/check.sh"]}},
    )
    with pytest.raises(RuntimeError):
        verification_commands(ctx)
