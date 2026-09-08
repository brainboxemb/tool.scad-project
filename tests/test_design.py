from pathlib import Path

from scad_project.design import (
    DesignDocument,
    DesignRender,
    _camera_args,
    _copy_source_assets,
    _generate_markdown,
    parse_design_document,
)


def _document(tmp_path: Path, body: str) -> DesignDocument:
    component = tmp_path / "example"
    design = component / "design"
    design.mkdir(parents=True)
    (component / "example.scad").write_text(
        'module example_design(view="final") { cube(1); }\n',
        encoding="utf-8",
    )
    md = design / "design.md"
    md.write_text(body, encoding="utf-8")
    return DesignDocument(
        source_file=md,
        scope="project",
        relative_path=Path("example/design/design.md"),
    )


def _render(**overrides):
    values = dict(
        document=DesignDocument(
            Path("/tmp/design.md"),
            "project",
            Path("x/design/design.md"),
        ),
        block_start=0,
        block_end=1,
        kind="inline",
        image="view.png",
        alt="View",
        source=None,
        module=None,
        view=None,
        inline_code="cube(1);",
        vpr=None,
        vpt=None,
        vpd=None,
        size=None,
    )
    values.update(overrides)
    return DesignRender(**values)


def test_render_defaults_and_automatic_image_names(tmp_path: Path):
    document = _document(
        tmp_path,
        """# Example

<!-- scad-render-defaults
module: example_design
vpr: [70, 0, 35]
-->

<!-- scad-render
view: base
-->

<!-- scad-render
view: final
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert [r.image for r in renders] == ["01-base.png", "02-final.png"]
    assert all(r.module == "example_design" for r in renders)
    assert all(r.vpr == [70.0, 0.0, 35.0] for r in renders)


def test_render_override_wins_over_defaults(tmp_path: Path):
    document = _document(
        tmp_path,
        """# Example

<!-- scad-render-defaults
module: example_design
vpr: [70, 0, 35]
size: [640, 480]
-->

<!-- scad-render
view: close-up
size: [800, 600]
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert renders[0].size == [800, 600]


def test_generated_markdown_removes_defaults_and_replaces_render(tmp_path: Path):
    document = _document(
        tmp_path,
        """# Example

<!-- scad-render-defaults
module: example_design
-->

<!-- scad-render
view: base
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    source = document.source_file.read_text(encoding="utf-8")
    generated = _generate_markdown(source, renders)

    assert "![Base](img/01-base.png)" in generated
    assert "scad-render-defaults" not in generated
    assert "<!-- scad-render" not in generated


def test_legacy_scad_design_remains_supported(tmp_path: Path):
    document = _document(
        tmp_path,
        """# Example

<!-- scad-design
type: source-view
module: example_design
view: base
image: old-name.png
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert renders[0].image == "old-name.png"


def test_vpr_only_uses_orientation_and_auto_fit():
    args = _camera_args(_render(vpr=[70.0, 0.0, 35.0]))
    assert "--autocenter" in args
    assert "--viewall" in args
    assert any(arg.startswith("--camera=") for arg in args)


def test_exact_camera_does_not_auto_fit():
    args = _camera_args(
        _render(
            vpr=[70.0, 0.0, 35.0],
            vpt=[1.0, 2.0, 3.0],
            vpd=400.0,
        )
    )
    assert "--autocenter" not in args
    assert "--viewall" not in args


def test_generated_docs_copy_static_assets(tmp_path: Path):
    source_dir = tmp_path / "source" / "design"
    source_dir.mkdir(parents=True)
    source_doc = source_dir / "design.md"
    source_doc.write_text("# Design\n", encoding="utf-8")
    (source_dir / "img").mkdir()
    (source_dir / "img" / "legacy.png").write_bytes(b"legacy")

    out_doc = tmp_path / "build" / "design.md"
    out_doc.parent.mkdir(parents=True)
    document = DesignDocument(
        source_doc,
        "external",
        Path("design/design.md"),
        "example",
    )

    _copy_source_assets(document, out_doc)
    assert (out_doc.parent / "img" / "legacy.png").read_bytes() == b"legacy"
