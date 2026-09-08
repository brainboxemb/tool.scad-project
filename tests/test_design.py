from pathlib import Path

from scad_project.design import DesignDocument, parse_design_document


def test_source_view(tmp_path: Path):
    component = tmp_path / "example"
    design = component / "design"
    design.mkdir(parents=True)

    (component / "example.scad").write_text(
        'module example_design(view="final") { cube(1); }\n',
        encoding="utf-8",
    )

    md = design / "design.md"
    md.write_text(
        """# Example

<!-- scad-design
type: source-view
module: example_design
view: base
image: 01-base.png
-->
""",
        encoding="utf-8",
    )

    document = DesignDocument(
        source_file=md,
        scope="project",
        relative_path=Path("example/design/design.md"),
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert renders[0].view == "base"
