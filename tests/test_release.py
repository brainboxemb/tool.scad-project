from pathlib import Path
import os
import zipfile

from scad_project.config import ProjectContext
from scad_project.release import package_release, release_asset_prefix


def context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo.project"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "verification": {"output_root": "vrf/out"},
            "publication": {
                "release": {
                    "branch_prefix": "rel",
                    "tag_pattern": "v*",
                }
            },
        },
    )


def seed_outputs(tmp_path: Path) -> None:
    (tmp_path / "bld" / "png").mkdir(parents=True)
    (tmp_path / "bld" / "stl").mkdir(parents=True)
    (tmp_path / "vrf" / "out" / "png").mkdir(parents=True)

    (tmp_path / "bld" / "README.md").write_text("build index\n", encoding="utf-8")
    (tmp_path / "bld" / "png" / "preview.png").write_bytes(b"PNG-demo")
    (tmp_path / "bld" / "stl" / "part-b.stl").write_text("solid b\n", encoding="utf-8")
    (tmp_path / "bld" / "stl" / "part-a.stl").write_text("solid a\n", encoding="utf-8")
    (tmp_path / "vrf" / "out" / "README.md").write_text("verification\n", encoding="utf-8")
    (tmp_path / "vrf" / "out" / "png" / "fit.png").write_bytes(b"PNG-fit")


def test_release_asset_prefix_uses_project_and_version(tmp_path: Path):
    assert release_asset_prefix(context(tmp_path), "v0.1.0") == "demo.project-v0.1.0"


def test_package_release_creates_expected_assets(tmp_path: Path):
    seed_outputs(tmp_path)
    artifacts = package_release(context(tmp_path), "v0.1.0")

    assert artifacts.build_bundle.name == "demo.project-v0.1.0-build.zip"
    assert artifacts.verification_bundle.name == "demo.project-v0.1.0-verification.zip"
    assert artifacts.stl_bundle is not None
    assert artifacts.stl_bundle.name == "demo.project-v0.1.0-stl.zip"
    assert artifacts.checksums.name == "SHA256SUMS.txt"
    assert all(path.is_file() for path in artifacts.assets)

    with zipfile.ZipFile(artifacts.build_bundle) as archive:
        assert archive.namelist() == [
            "README.md",
            "png/preview.png",
            "stl/part-a.stl",
            "stl/part-b.stl",
        ]

    with zipfile.ZipFile(artifacts.stl_bundle) as archive:
        assert archive.namelist() == ["part-a.stl", "part-b.stl"]

    checksum_lines = artifacts.checksums.read_text(encoding="utf-8").splitlines()
    assert len(checksum_lines) == 3
    assert checksum_lines == sorted(checksum_lines, key=lambda line: line.split("  ", 1)[1])
    assert any(line.endswith("  demo.project-v0.1.0-build.zip") for line in checksum_lines)
    assert any(line.endswith("  demo.project-v0.1.0-stl.zip") for line in checksum_lines)
    assert any(
        line.endswith("  demo.project-v0.1.0-verification.zip")
        for line in checksum_lines
    )


def test_release_zip_metadata_is_normalized(tmp_path: Path):
    seed_outputs(tmp_path)
    artifacts = package_release(context(tmp_path), "v0.1.0")

    with zipfile.ZipFile(artifacts.build_bundle) as archive:
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.filename == info.filename.replace("\\", "/")


def test_release_bundles_ignore_source_file_mtime(tmp_path: Path):
    seed_outputs(tmp_path)
    ctx = context(tmp_path)

    first = package_release(ctx, "v0.1.0", tmp_path / "release-a")
    first_build = first.build_bundle.read_bytes()
    first_verification = first.verification_bundle.read_bytes()
    first_stl = first.stl_bundle.read_bytes() if first.stl_bundle else b""

    for file in (tmp_path / "bld").rglob("*"):
        if file.is_file():
            os.utime(file, (1_900_000_000, 1_900_000_000))
    for file in (tmp_path / "vrf" / "out").rglob("*"):
        if file.is_file():
            os.utime(file, (1_900_000_000, 1_900_000_000))

    second = package_release(ctx, "v0.1.0", tmp_path / "release-b")

    assert second.build_bundle.read_bytes() == first_build
    assert second.verification_bundle.read_bytes() == first_verification
    assert second.stl_bundle is not None
    assert second.stl_bundle.read_bytes() == first_stl
    assert second.checksums.read_text(encoding="utf-8") == first.checksums.read_text(
        encoding="utf-8"
    )


def test_stl_bundle_is_omitted_when_project_has_no_stls(tmp_path: Path):
    seed_outputs(tmp_path)
    for file in (tmp_path / "bld" / "stl").glob("*.stl"):
        file.unlink()

    artifacts = package_release(context(tmp_path), "v0.1.0")

    assert artifacts.stl_bundle is None
    assert not (artifacts.output_dir / "demo.project-v0.1.0-stl.zip").exists()
    assert len(artifacts.checksums.read_text(encoding="utf-8").splitlines()) == 2
