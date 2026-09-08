from pathlib import Path

from scad_project.design import (
    DesignDocument,
    _materialize_markdown,
    parse_design_document,
)


def test_source_view_declaration_materializes_to_image(tmp_path: Path):
    component = tmp_path / "component"
    design = component / "design"
    design.mkdir(parents=True)

    (component / "component.scad").write_text(
        'module component_design(view="final") { cube(1); }\n',
        encoding="utf-8",
    )

    source = design / "design.md"
    source.write_text(
        """# Component

<!-- scad-design
type: source-view
module: component_design
view: base
image: 01-base.png
alt: Base geometry
-->
""",
        encoding="utf-8",
    )

    document = DesignDocument(
        source_file=source,
        scope="project",
        relative_path=Path("components/component/design/design.md"),
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert len(renders) == 1

    result = _materialize_markdown(source.read_text(), renders)
    assert "![Base geometry](img/01-base.png)" in result
    assert "<!-- scad-design" not in result
