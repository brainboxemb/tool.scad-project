"""Exact SCons build dependency provenance.

Checks:
Target provenance is derived from the existing scanned SCons source manifest,
attributes each used external source to the deepest owner-local dependency
worktree, preserves independent pins of the same repository, and skips
persistent output for unversioned local contexts.

Testing approach:
The tests construct small local Git repositories with root and nested external
dependencies, feed a synthetic already-scanned build manifest to the production
provenance writer, and assert owner/path/ref/revision/source attribution without
network access or CAD rendering.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import scad_project.dependency_provenance as dependency_provenance
from scad_project.config import ProjectContext


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
    ).strip()


def _init_repo(
    path: Path,
    *,
    project_yml: str,
    files: dict[str, str],
    remote: str,
) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "provenance-test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "config",
            "user.email",
            "provenance-test@example.invalid",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True,
    )
    (path / "project.yml").write_text(project_yml, encoding="utf-8")
    for relative, content in files.items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    return _git(path, "rev-parse", "HEAD")


def _context(root: Path) -> ProjectContext:
    return ProjectContext(
        root,
        root / "project.scad.yml",
        {
            "project": {"name": "provenance-fixture"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "build_engine": {"engine": "scons"},
        },
    )


def test_provenance_uses_scanned_sources_and_keeps_independent_owner_pins(
    tmp_path: Path,
):
    root = tmp_path / "project"
    root_project = """schema_version: 1
project:
  name: fixture
dependencies:
  - name: lib.scad.mechint
    role: external
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.mechint.git
    path: ext/lib.scad.mechint
    ref: v0.1.6
  - name: lib.scad.util
    role: external
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.util.git
    path: ext/lib.scad.util
    ref: v0.2.0
"""
    source_sha = _init_repo(
        root,
        project_yml=root_project,
        files={"dsg/render.scad": "cube(1);\n"},
        remote="https://github.com/example/fixture.git",
    )

    mechint = root / "ext/lib.scad.mechint"
    mechint_project = """schema_version: 1
project:
  name: lib.scad.mechint
dependencies:
  - name: lib.scad.util
    role: external
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.util.git
    path: ext/lib.scad.util
    ref: v0.1.0
"""
    mechint_sha = _init_repo(
        mechint,
        project_yml=mechint_project,
        files={"openscad/mechint.scad": "module mechint() {}\n"},
        remote="https://github.com/brainboxemb/lib.scad.mechint.git",
    )

    project_util = root / "ext/lib.scad.util"
    project_util_sha = _init_repo(
        project_util,
        project_yml="schema_version: 1\nproject:\n  name: lib.scad.util\n",
        files={"openscad/transform.scad": "module transform() {}\n"},
        remote="https://github.com/brainboxemb/lib.scad.util.git",
    )

    nested_util = mechint / "ext/lib.scad.util"
    nested_util_sha = _init_repo(
        nested_util,
        project_yml="schema_version: 1\nproject:\n  name: lib.scad.util\n",
        files={"openscad/inspection.scad": "module inspection() {}\n"},
        remote="https://github.com/brainboxemb/lib.scad.util.git",
    )

    manifest = root / ".cache/scad-project/state/build-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "targets": [
                    {
                        "source": "dsg/render.scad",
                        "output": "bld/stl/combined.stl",
                        "sources": [
                            "dsg/render.scad",
                            "ext/lib.scad.mechint/openscad/mechint.scad",
                            "ext/lib.scad.util/openscad/transform.scad",
                            "ext/lib.scad.mechint/ext/lib.scad.util/openscad/inspection.scad",
                        ],
                    },
                    {
                        "source": "dsg/render.scad",
                        "output": "bld/stl/project-only.stl",
                        "sources": ["dsg/render.scad"],
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    output = root / ".cache/scad-project/state/dependency-provenance.json"
    written = dependency_provenance.write_dependency_provenance(
        _context(root),
        manifest,
        output,
    )
    assert written == output

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == dependency_provenance.SCHEMA_NAME
    assert payload["schema_version"] == 1
    assert payload["source_revision"] == source_sha
    assert payload["build_manifest"] == ".cache/scad-project/state/build-manifest.json"

    combined = payload["targets"][0]
    assert combined["output"] == "bld/stl/combined.stl"
    dependencies = {
        (item["owner_path"], item["dependency_path"]): item
        for item in combined["dependencies"]
    }
    assert dependencies[(".", "ext/lib.scad.mechint")]["revision"] == mechint_sha
    assert dependencies[(".", "ext/lib.scad.util")]["revision"] == project_util_sha
    assert (
        dependencies[("ext/lib.scad.mechint", "ext/lib.scad.util")]["revision"]
        == nested_util_sha
    )

    direct_util = dependencies[(".", "ext/lib.scad.util")]
    nested = dependencies[("ext/lib.scad.mechint", "ext/lib.scad.util")]
    assert direct_util["repository"] == nested["repository"]
    assert direct_util["revision"] != nested["revision"]
    assert direct_util["declared_ref"] == "v0.2.0"
    assert nested["declared_ref"] == "v0.1.0"
    assert direct_util["used_sources"] == [
        "ext/lib.scad.util/openscad/transform.scad"
    ]
    assert nested["used_sources"] == [
        "ext/lib.scad.mechint/ext/lib.scad.util/openscad/inspection.scad"
    ]
    assert payload["targets"][1]["dependencies"] == []


def test_unversioned_local_context_skips_persistent_provenance(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"targets": []}\n', encoding="utf-8")

    def fail_source_revision(context):
        raise RuntimeError("no exact source")

    monkeypatch.setattr(
        dependency_provenance,
        "resolve_source_revision",
        fail_source_revision,
    )

    output = dependency_provenance.write_dependency_provenance(
        _context(tmp_path),
        manifest,
        tmp_path / "dependency-provenance.json",
    )

    assert output is None
    assert "persistent SCAD dependency provenance skipped" in capsys.readouterr().out
