from pathlib import Path
from scad_project.design import parse_design_file

def test_source_view(tmp_path: Path):
    component = tmp_path / "example"
    design = component / "design"
    design.mkdir(parents=True)
    (component / "example.scad").write_text(
        'module example_design(view="final") { cube(1); }\n'
    )
    md = design / "design.md"
    md.write_text('''# Example

<!-- scad-design
type: source-view
module: example_design
view: base
image: 01-base.png
-->
''')
    renders, errors = parse_design_file(md)
    assert errors == []
    assert renders[0].view == "base"
