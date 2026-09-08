from pathlib import Path
from scad_project.config import ProjectContext
from scad_project.docs import lint_docs

def test_file_header_required(tmp_path: Path):
    root = tmp_path / "dsg" / "openscad"
    root.mkdir(parents=True)
    (root / "part.scad").write_text(
        "// Module: part()\nmodule part(){cube(1);}\n"
    )
    ctx = ProjectContext(
        tmp_path, tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
        },
    )
    errors = lint_docs(ctx, run_docsgen=False)
    assert errors
