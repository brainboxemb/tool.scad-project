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
