"""External design documentation policy

Checks:
External-library design documentation is included by default, can be disabled with a
boolean setting, rejects invalid setting types, and is actually filtered out when
disabled. The generated design index must also explain that external documentation was
intentionally omitted.

Testing approach:
The tests use small project and external document objects. For cases that need a
controlled discovery/build result, pytest's `monkeypatch` fixture temporarily replaces
the internal discovery or build function with a small predictable function, then
automatically restores the original after the test.
"""

from pathlib import Path

import pytest

from scad_project import design as design_engine
from scad_project.design import DesignDocument
from scad_project.design_policy import (
    _design_discovery_policy,
    build_design,
    include_external_designs,
)


class DummyContext:
    def __init__(self, root: Path, include_externals=None):
        self.root = root
        self.config = {
            "paths": {"build_root": "bld"},
        }
        if include_externals is not None:
            self.config["design"] = {"include_externals": include_externals}

    def path(self, value):
        return self.root / value


def _doc(tmp_path: Path, scope: str) -> DesignDocument:
    return DesignDocument(
        source_file=tmp_path / f"{scope}.md",
        scope=scope,
        relative_path=Path(f"{scope}/design/design.md"),
        external_name="example-lib" if scope == "external" else None,
    )


def test_include_externals_defaults_to_true(tmp_path: Path):
    assert include_external_designs(DummyContext(tmp_path)) is True


def test_include_externals_requires_boolean(tmp_path: Path):
    context = DummyContext(tmp_path)
    context.config["design"] = {"include_externals": "no"}
    with pytest.raises(RuntimeError, match="must be true or false"):
        include_external_designs(context)


def test_discovery_policy_filters_external_documents(monkeypatch, tmp_path: Path):
    project = _doc(tmp_path, "project")
    external = _doc(tmp_path, "external")

    def discover(_context):
        return [project, external]

    monkeypatch.setattr(design_engine, "discover_design_documents", discover)
    context = DummyContext(tmp_path, include_externals=False)

    with _design_discovery_policy(context):
        selected = design_engine.discover_design_documents(context)
        assert selected == [project]

    assert design_engine.discover_design_documents(context) == [project, external]


def test_build_index_explains_intentional_omission(monkeypatch, tmp_path: Path):
    context = DummyContext(tmp_path, include_externals=False)

    def fake_build(_context):
        output = tmp_path / "bld" / "design"
        output.mkdir(parents=True)
        (output / "README.md").write_text(
            "# Design documentation\n\n## Externals\n\n"
            "- No external design documents found.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(design_engine, "build_design", fake_build)
    build_design(context)

    text = (tmp_path / "bld" / "design" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "intentionally omitted" in text
    assert "design.include_externals: false" in text
