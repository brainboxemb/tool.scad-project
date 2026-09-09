from pathlib import Path

import scad_project.build as build_module
from scad_project.config import ProjectContext


def _context(tmp_path: Path, *, watermark: bool) -> ProjectContext:
    source = tmp_path / "dsg" / "render" / "assembly.scad"
    source.parent.mkdir(parents=True)
    source.write_text("cube([1,1,1]);\n", encoding="utf-8")

    config = {
        "project": {"name": "demo"},
        "paths": {"design_root": "dsg", "build_root": "bld"},
        "openscad": {"image_size": [800, 600]},
        "externals": [],
        "builds": [
            {
                "name": "assembly-png",
                "source": "dsg/render/assembly.scad",
                "output": "bld/png/assembly.png",
            }
        ],
    }
    if watermark:
        config["rendering"] = {
            "watermark": {"text": "© 2026 brainboxemb"}
        }

    return ProjectContext(tmp_path, tmp_path / "project.yml", config)


def test_png_build_without_watermark_uses_direct_output(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, *, cwd):
        calls.append(args)
        output = Path(args[args.index("-o") + 1])
        output.write_bytes(b"png")

    monkeypatch.setattr(build_module, "run_checked", fake_run)

    build_module.build_project(_context(tmp_path, watermark=False))

    output = tmp_path / "bld" / "png" / "assembly.png"
    assert output.read_bytes() == b"png"
    assert len(calls) == 1
    assert "openscad" in calls[0]
    assert str(output) in calls[0]


def test_png_build_with_watermark_calls_public_tool(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, *, cwd):
        calls.append(args)
        if args[0] == "scad-image-watermark":
            raw = Path(args[1])
            output = Path(args[2])
            assert raw.read_bytes() == b"raw-png"
            output.write_bytes(b"watermarked-png")
            return

        output = Path(args[args.index("-o") + 1])
        output.write_bytes(b"raw-png")

    monkeypatch.setattr(build_module, "run_checked", fake_run)

    build_module.build_project(_context(tmp_path, watermark=True))

    output = tmp_path / "bld" / "png" / "assembly.png"
    raw = tmp_path / "bld" / "png" / ".assembly.unwatermarked.png"

    assert output.read_bytes() == b"watermarked-png"
    assert not raw.exists()
    assert len(calls) == 2
    assert calls[1] == [
        "scad-image-watermark",
        str(raw),
        str(output),
        "--text",
        "© 2026 brainboxemb",
    ]


def test_directory_build_discovers_render_and_export_entrypoints(tmp_path, monkeypatch):
    render_dir = tmp_path / "dsg" / "openscad" / "render"
    export_dir = tmp_path / "dsg" / "openscad" / "export"
    render_dir.mkdir(parents=True)
    export_dir.mkdir(parents=True)

    (render_dir / "front.scad").write_text("cube([1,1,1]);\n", encoding="utf-8")
    (export_dir / "part.scad").write_text("cube([1,1,1]);\n", encoding="utf-8")

    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "render_root": "dsg/openscad/render",
                "export_root": "dsg/openscad/export",
            },
            "openscad": {"image_size": [800, 600]},
            "externals": [],
        },
    )

    calls = []

    def fake_run(args, *, cwd):
        calls.append(args)
        output = Path(args[args.index("-o") + 1])
        output.write_bytes(b"output")

    monkeypatch.setattr(build_module, "run_checked", fake_run)

    build_module.build_project(ctx)

    assert (tmp_path / "bld" / "png" / "front.png").is_file()
    assert (tmp_path / "bld" / "stl" / "part.stl").is_file()
    assert len(calls) == 2


def test_render_profile_multi_size_and_image_size(tmp_path, monkeypatch):
    render_dir = tmp_path / "dsg" / "openscad" / "render"
    render_dir.mkdir(parents=True)

    (render_dir / "middle_coupler.scad").write_text(
        "cube([1,1,1]);\n",
        encoding="utf-8",
    )
    (render_dir / "render.yml").write_text(
        """defaults:
  image_size: [2560, 1440]

profiles:
  multi-size:
    sizes: [small, medium, large]
    image_size: [1800, 1200]
    files:
      - middle_coupler.scad
""",
        encoding="utf-8",
    )

    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "render_root": "dsg/openscad/render",
            },
            "openscad": {"image_size": [800, 600]},
            "externals": [],
        },
    )

    calls = []

    def fake_run(args, *, cwd):
        calls.append(args)
        output = Path(args[args.index("-o") + 1])
        output.write_bytes(b"png")

    monkeypatch.setattr(build_module, "run_checked", fake_run)

    build_module.build_project(ctx)

    for size in ("small", "medium", "large"):
        assert (
            tmp_path / "bld" / "png" / f"middle-coupler-{size}.png"
        ).is_file()

    assert len(calls) == 3
    for size, call in zip(("small", "medium", "large"), calls):
        assert "--imgsize=1800,1200" in call
        assert "-D" in call
        assert f'size="{size}"' in call


def test_export_profile_multi_size(tmp_path, monkeypatch):
    export_dir = tmp_path / "dsg" / "openscad" / "export"
    export_dir.mkdir(parents=True)

    (export_dir / "middle_coupler.scad").write_text(
        "cube([1,1,1]);\n",
        encoding="utf-8",
    )
    (export_dir / "export.yml").write_text(
        """profiles:
  multi-size:
    sizes: [small, medium, large]
    files:
      - middle_coupler.scad
""",
        encoding="utf-8",
    )

    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "export_root": "dsg/openscad/export",
            },
            "externals": [],
        },
    )

    calls = []

    def fake_run(args, *, cwd):
        calls.append(args)
        output = Path(args[args.index("-o") + 1])
        output.write_bytes(b"stl")

    monkeypatch.setattr(build_module, "run_checked", fake_run)

    build_module.build_project(ctx)

    for size in ("small", "medium", "large"):
        assert (
            tmp_path / "bld" / "stl" / f"middle-coupler-{size}.stl"
        ).is_file()

    assert len(calls) == 3


def test_directory_profile_rejects_duplicate_file_assignment(tmp_path):
    render_dir = tmp_path / "dsg" / "openscad" / "render"
    render_dir.mkdir(parents=True)
    (render_dir / "part.scad").write_text("cube(1);\n", encoding="utf-8")
    (render_dir / "render.yml").write_text(
        """profiles:
  first:
    files: [part.scad]
  second:
    files: [part.scad]
""",
        encoding="utf-8",
    )

    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "render_root": "dsg/openscad/render",
            },
            "externals": [],
        },
    )

    try:
        build_module.build_project(ctx)
    except RuntimeError as exc:
        assert "assigned to more than one profile" in str(exc)
    else:
        raise AssertionError("Expected duplicate profile assignment to fail")
