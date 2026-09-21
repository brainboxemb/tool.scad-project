"""Moon capability output and launcher policy

Checks:
Shared Migration-005 Moon capability tasks expose only stable materialized
outputs. Optional SCons state files must not be required outputs. The production-owned
Build dependency-provenance report is the one domain-evidence file explicitly
retained as a Moon output so whole-capability hydration preserves exact external
source identity. Shared capability commands must also
use the runtime-guaranteed `python3` executable rather than assuming a `python`
alias exists in the immutable SCAD toolchain image.

Testing approach:
Load the real shared Moon task YAML and assert the public output and command
contracts for `scad.docs`, `scad.build` and `scad.verify`. Also reject cache-state paths and any domain-evidence output other than the
production-owned dependency provenance file.
"""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TASKS_FILE = ROOT / "moon" / "tasks" / "scad.yml"


def _tasks() -> dict:
    payload = yaml.safe_load(TASKS_FILE.read_text(encoding="utf-8"))
    return payload["tasks"]


def test_shared_capability_outputs_do_not_require_optional_engine_state() -> None:
    tasks = _tasks()

    assert tasks["scad.docs"]["outputs"] == [
        "bld/design/**",
        "bld/evidence/executions/scad-docs/**",
    ]
    assert tasks["scad.build"]["outputs"] == [
        "bld/png/**",
        "bld/svg/**",
        "bld/stl/**",
        "bld/drawing/**",
        "bld/evidence/executions/scad-build/**",
        "bld/evidence/domain/dependency-provenance.json",
    ]
    assert tasks["scad.verify"]["outputs"] == ["vrf/out/**"]

    allowed_domain_output = "bld/evidence/domain/dependency-provenance.json"
    for task_name, task in tasks.items():
        for output in task["outputs"]:
            assert not output.startswith(".cache/scad-project/")
            if "/evidence/domain/" in output:
                assert task_name == "scad.build"
                assert output == allowed_domain_output


def test_shared_capability_commands_use_runtime_python3() -> None:
    tasks = _tasks()

    expected_actions = {
        "scad.docs": "design-build",
        "scad.build": "build",
        "scad.verify": "verify",
    }
    for task_name, action in expected_actions.items():
        command = tasks[task_name]["command"]
        assert command == (
            "python3 tools/tool.scad-project/scripts/run_scad_capability.py "
            f"{action}"
        )
        assert not command.startswith("python ")
