from pathlib import Path

from scad_project.design import (
    DesignDocument,
    DesignRender,
    _render_args,
    parse_design_document,
)


class DummyContext:
    def __init__(self):
        self.config = {
            "openscad": {
                "common_flags": ["--enable=object-function"],
                "render_flags": ["--render"],
            },
            "pythonscad": {
                "common_flags": ["--trust-python"],
                "render_flags": ["--render"],
            },
        }


def _document(tmp_path: Path, source_name: str, source_text: str, markdown: str):
    component = tmp_path / "component"
    design = component / "design"
    design.mkdir(parents=True)

    (component / source_name).write_text(source_text, encoding="utf-8")
    md = design / "design.md"
    md.write_text(markdown, encoding="utf-8")

    return DesignDocument(
        source_file=md,
        scope="project",
        relative_path=Path("component/design/design.md"),
    )


def test_openscad_engine_is_inferred_from_scad_source(tmp_path: Path):
    document = _document(
        tmp_path,
        "component.scad",
        'module component_design(view="final") { cube(1); }\n',
        """# Example

<!-- scad-render-defaults
module: component_design
-->

<!-- scad-render
view: final
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert renders[0].engine == "openscad"
    assert renders[0].image == "01-final.png"


def test_pythonscad_engine_is_inferred_from_py_source(tmp_path: Path):
    document = _document(
        tmp_path,
        "render.py",
        "from pythonscad import *\nshow(cube([1,1,1]))\n",
        """# Example

<!-- scad-render-defaults
source: render.py
-->

<!-- scad-render
view: final
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert renders[0].engine == "pythonscad"
    assert renders[0].module is None


def test_explicit_engine_wins_over_suffix_inference(tmp_path: Path):
    document = _document(
        tmp_path,
        "render.py",
        "print('probe')\n",
        """# Example

<!-- scad-render-defaults
engine: openscad
source: render.py
module: wrapper
-->

<!-- scad-render
view: final
-->
""",
    )

    renders, errors = parse_design_document(document)
    assert errors == []
    assert renders[0].engine == "openscad"


def test_pythonscad_command_injects_design_view(tmp_path: Path):
    source = tmp_path / "render.py"
    source.write_text("print('x')\n", encoding="utf-8")

    render = DesignRender(
        document=DesignDocument(
            source_file=tmp_path / "design.md",
            scope="project",
            relative_path=Path("design/design.md"),
        ),
        block_start=0,
        block_end=1,
        engine="pythonscad",
        kind="source-view",
        image="01-final.png",
        alt="Final",
        source=source,
        module=None,
        view="Final clamp",
        inline_code=None,
        vpr=None,
        vpt=None,
        vpd=None,
        size=None,
    )

    args = _render_args(
        DummyContext(),
        render,
        None,
        tmp_path / "out.png",
        [640, 480],
    )

    assert args[0:3] == ["xvfb-run", "-a", "pythonscad"]
    assert "--trust-python" in args
    assert "-D" in args
    assert 'design_view="Final clamp"' in args
    assert "--imgsize=640,480" in args


def test_inline_pythonscad_is_rejected(tmp_path: Path):
    component = tmp_path / "component"
    design = component / "design"
    design.mkdir(parents=True)
    md = design / "design.md"
    md.write_text(
        """# Example

<!-- scad-render
engine: pythonscad
type: inline
view: final
-->

```openscad
cube(1);
```
""",
        encoding="utf-8",
    )

    document = DesignDocument(
        source_file=md,
        scope="project",
        relative_path=Path("component/design/design.md"),
    )
    _, errors = parse_design_document(document)
    assert any("inline PythonSCAD" in error for error in errors)
