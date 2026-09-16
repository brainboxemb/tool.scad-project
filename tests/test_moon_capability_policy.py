"""Moon capability output and launcher policy

Checks:
Shared Migration-005 Moon capability tasks expose only stable materialized
outputs. Optional SCons state files and optional domain-evidence reports must not
be required outputs, because direct-engine consumers and verification commands
without SCons targets do not produce them. Shared capability commands must also
use the runtime-guaranteed `python3` executable rather than assuming a `python`
alias exists in the immutable SCAD toolchain image.

Testing approach:
Load the real shared Moon task YAML and assert the public output and command
contracts for `scad.docs`, `scad.build` and `scad.verify`. Also reject cache-state
and optional domain-report paths from every declared output list.
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
        "bld/stl/**",
        "bld/evidence/executions/scad-build/**",
    ]
    assert tasks["scad.verify"]["outputs"] == ["vrf/out/**"]

    for task in tasks.values():
        for output in task["outputs"]:
            assert not output.startswith(".cache/scad-project/")
            assert "/evidence/domain/" not in output


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
