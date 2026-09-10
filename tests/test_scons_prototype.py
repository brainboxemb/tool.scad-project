from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


SCONSTRUCT = r'''
from pathlib import Path
import hashlib

from SCons.Script import ARGUMENTS, CacheDir, Command, Default
from scad_project.openscad_deps import scan_openscad_dependencies

cache_dir = ARGUMENTS["CACHE_DIR"]
log_path = Path(ARGUMENTS["LOG"])
CacheDir(cache_dir)


def render(target, source, env):
    target_path = Path(str(target[0]))
    target_path.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    for node in source:
        digest.update(Path(str(node)).read_bytes())

    target_path.write_text(digest.hexdigest() + "\n", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(target_path.name + "\n")
    return 0


targets = []
for name in ("a", "b"):
    source = Path("src") / f"{name}.scad"
    dependencies = scan_openscad_dependencies(source)
    target = Path("bld") / f"{name}.out"
    targets.extend(
        Command(
            str(target),
            [str(source), *[str(path) for path in dependencies]],
            render,
        )
    )

Default(targets)
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_scons(project: Path, cache: Path, log: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            "scons",
            "-Q",
            f"CACHE_DIR={cache}",
            f"LOG={log}",
        ],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    return result


def _clean_runner_state(project: Path, log: Path) -> None:
    shutil.rmtree(project / "bld", ignore_errors=True)
    (project / ".sconsign.dblite").unlink(missing_ok=True)
    log.unlink(missing_ok=True)


def _actions(log: Path) -> list[str]:
    if not log.is_file():
        return []
    return log.read_text(encoding="utf-8").splitlines()


def test_cache_restores_complete_outputs_and_rebuilds_only_changed_dependency(tmp_path):
    if shutil.which("scons") is None:
        pytest.skip("SCons experiment dependency is not installed")

    project = tmp_path / "project"
    cache = tmp_path / "scons-cache"
    log = project / "actions.log"
    project.mkdir()

    _write(project / "SConstruct", textwrap.dedent(SCONSTRUCT))
    _write(project / "src" / "a.scad", "include <shared.scad>\ncube(1);\n")
    _write(project / "src" / "shared.scad", "include <nested.scad>\n")
    _write(project / "src" / "nested.scad", "A = 1;\n")
    _write(project / "src" / "b.scad", "sphere(1);\n")

    first = _run_scons(project, cache, log)
    assert _actions(log) == ["a.out", "b.out"]
    assert (project / "bld" / "a.out").is_file()
    assert (project / "bld" / "b.out").is_file()
    assert cache.is_dir()
    assert "render(" in first.stdout

    # Simulate a fresh GitHub-hosted runner: generated outputs and SCons state
    # are gone, but an Actions-restored CacheDir is still available.
    _clean_runner_state(project, log)

    second = _run_scons(project, cache, log)
    assert _actions(log) == []
    assert (project / "bld" / "a.out").is_file()
    assert (project / "bld" / "b.out").is_file()
    assert "retrieved" in second.stdout.lower()

    # A transitive dependency of only target A changes. Start clean again while
    # keeping the same cache: A must execute, B must still be restored.
    _write(project / "src" / "nested.scad", "A = 2;\n")
    _clean_runner_state(project, log)

    third = _run_scons(project, cache, log)
    assert _actions(log) == ["a.out"]
    assert (project / "bld" / "a.out").is_file()
    assert (project / "bld" / "b.out").is_file()
    assert "b.out" in third.stdout
    assert "retrieved" in third.stdout.lower()
