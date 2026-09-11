"""Project verification targets and commands

Checks:
Verification commands in `project.yml` must be explicit argument lists such as
`["python3", "check.py"]`. A single shell command string is rejected so command
execution does not depend on shell parsing, quoting or command injection behavior.
Verification-only OpenSCAD targets use their own source/output roots and image size,
remain separate from normal `bld/` outputs, and are built before project-specific
verification commands run.

Testing approach:
The tests create minimal project configurations containing supported and rejected
command forms, plus a small verification render directory with a normal `render.yml`
profile. They inspect the resolved target model without invoking OpenSCAD. For execution
ordering, pytest's `monkeypatch` fixture temporarily replaces the target builder and
process runner with lightweight recorders.
"""

from pathlib import Path
import pytest

from scad_project.config import ProjectContext
import scad_project.verification as verification
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


def test_verification_targets_use_separate_output_root_and_image_size(tmp_path: Path):
    render_root = tmp_path / "vrf" / "openscad"
    render_root.mkdir(parents=True)
    (render_root / "fit_section.scad").write_text("cube(1);\n", encoding="utf-8")
    (render_root / "render.yml").write_text(
        "profiles:\n"
        "  sized:\n"
        "    files: [fit_section.scad]\n"
        "    sizes: [small, medium]\n",
        encoding="utf-8",
    )

    ctx = ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "openscad": {"image_size": [1600, 1000]},
            "verification": {
                "render_root": "vrf/openscad",
                "output_root": "vrf/out",
                "image_size": [1280, 720],
            },
        },
    )

    targets = verification.verification_targets(ctx)

    assert [target["output"].relative_to(tmp_path).as_posix() for target in targets] == [
        "vrf/out/png/fit-section-small.png",
        "vrf/out/png/fit-section-medium.png",
    ]
    assert [target["image_size"] for target in targets] == [(1280, 720), (1280, 720)]
    assert [target["definitions"] for target in targets] == [
        ['size="small"'],
        ['size="medium"'],
    ]
    assert not any(
        target["output"].is_relative_to(tmp_path / "bld")
        for target in targets
    )


def test_functional_verification_builds_targets_before_commands(tmp_path: Path, monkeypatch):
    ctx = ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={"verification": {"commands": [["bash", "scripts/check.sh"]]}},
    )
    calls: list[object] = []

    monkeypatch.setattr(
        verification,
        "build_verification_targets",
        lambda context: calls.append(("targets", context.root)),
    )
    monkeypatch.setattr(
        verification,
        "run_checked",
        lambda command, cwd: calls.append(("command", command, cwd)),
    )

    verification.run_functional_verification(ctx)

    assert calls == [
        ("targets", tmp_path),
        ("command", ["bash", "scripts/check.sh"], tmp_path),
    ]
