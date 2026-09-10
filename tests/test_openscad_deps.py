from pathlib import Path

import pytest

from scad_project.openscad_deps import (
    OpenScadDependencyError,
    direct_openscad_dependencies,
    referenced_openscad_paths,
    scan_openscad_dependencies,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_referenced_paths_ignore_commented_directives(tmp_path):
    source = _write(
        tmp_path / "main.scad",
        """// use <ignored-line.scad>
/* include <ignored-block.scad> */
use <first.scad>
include <second.scad>
""",
    )

    assert referenced_openscad_paths(source) == ["first.scad", "second.scad"]


def test_recursive_scan_follows_nested_dependencies_in_source_order(tmp_path):
    main = _write(
        tmp_path / "main.scad",
        "use <a.scad>\ninclude <b.scad>\n",
    )
    a = _write(tmp_path / "a.scad", "include <nested/c.scad>\n")
    c = _write(tmp_path / "nested" / "c.scad", "cube(1);\n")
    b = _write(tmp_path / "b.scad", "sphere(1);\n")

    assert scan_openscad_dependencies(main) == [a.resolve(), c.resolve(), b.resolve()]


def test_duplicate_and_cyclic_dependencies_are_returned_once(tmp_path):
    main = _write(
        tmp_path / "main.scad",
        "use <a.scad>\nuse <a.scad>\n",
    )
    a = _write(tmp_path / "a.scad", "include <b.scad>\ninclude <main.scad>\n")
    b = _write(tmp_path / "b.scad", "use <a.scad>\n")

    assert scan_openscad_dependencies(main) == [a.resolve(), b.resolve()]


def test_search_path_can_resolve_external_library_reference(tmp_path):
    project = tmp_path / "project"
    libraries = tmp_path / "libraries"
    main = _write(project / "main.scad", "use <demo/widget.scad>\n")
    widget = _write(libraries / "demo" / "widget.scad", "cube(1);\n")

    assert direct_openscad_dependencies(
        main,
        search_paths=[libraries],
    ) == [widget.resolve()]


def test_relative_external_dependency_is_followed_transitively(tmp_path):
    main = _write(
        tmp_path / "dsg" / "render" / "main.scad",
        "use <../components/adapter.scad>\n",
    )
    adapter = _write(
        tmp_path / "dsg" / "components" / "adapter.scad",
        "use <../ext/lib/demo.scad>\n",
    )
    external = _write(
        tmp_path / "dsg" / "ext" / "lib" / "demo.scad",
        "cube(1);\n",
    )

    assert scan_openscad_dependencies(main) == [
        adapter.resolve(),
        external.resolve(),
    ]


def test_missing_dependency_reports_owner_and_search_locations(tmp_path):
    main = _write(tmp_path / "main.scad", "include <missing.scad>\n")

    with pytest.raises(OpenScadDependencyError) as exc_info:
        scan_openscad_dependencies(main)

    message = str(exc_info.value)
    assert "missing.scad" in message
    assert str(main.resolve()) in message
