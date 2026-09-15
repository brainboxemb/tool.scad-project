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
