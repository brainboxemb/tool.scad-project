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
