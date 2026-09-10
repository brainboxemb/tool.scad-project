"""Release packages and atomic release publication

Checks:
A release creates deterministic build, verification and optional STL ZIP files plus
sorted SHA-256 checksums. ZIP metadata is normalized so file modification times do not
change the bundle bytes. Release publication refuses pre-existing release branches,
requires matching provenance, publishes build and verification branches as immutable
snapshots, and removes a newly created build branch if publishing verification fails.

Testing approach:
The packaging tests create small temporary build and verification trees and inspect the
real ZIP files and checksum file. Publication tests use pytest's `monkeypatch` fixture
to temporarily replace remote Git checks and pushes with controlled functions that
record or deliberately fail an operation. This exercises success and rollback logic
without creating real remote branches.
"""

from pathlib import Path
import os
import zipfile

import pytest

from scad_project.config import ProjectContext
import scad_project.release as release_module
from scad_project.release import (
    package_release,
    publish_release_branches,
    release_asset_prefix,
)


SOURCE_SHA = "0123456789abcdef0123456789abcdef01234567"


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


def seed_release_provenance(tmp_path: Path, *, version: str = "v0.1.0") -> None:
    (tmp_path / "bld").mkdir(parents=True, exist_ok=True)
    (tmp_path / "vrf" / "out").mkdir(parents=True, exist_ok=True)
    (tmp_path / "bld" / "publication-info.txt").write_text(
        "\n".join(
            [
                "Publication context : release",
                "Publication kind    : build",
                f"Publication branch  : rel/{version}/build",
                "Ref type            : tag",
                f"Ref                 : {version}",
                f"Commit              : {SOURCE_SHA}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "vrf" / "out" / "publication-info.txt").write_text(
        "\n".join(
            [
                "Publication context : release",
                "Publication kind    : verification",
                f"Publication branch  : rel/{version}/verification",
                "Ref type            : tag",
                f"Ref                 : {version}",
                f"Commit              : {SOURCE_SHA}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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
    """Prove bundle bytes stay reproducible when source mtimes differ."""
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


def test_publish_release_branches_preflights_and_publishes_both(
    tmp_path: Path,
    monkeypatch,
):
    seed_release_provenance(tmp_path)
    published: list[tuple[str, bool]] = []
    checked: list[str] = []

    def branch_exists(cwd: Path, branch: str) -> bool:
        checked.append(branch)
        return False

    def publish_snapshot(source_root, branch, message, *, immutable=False):
        published.append((branch, immutable))

    monkeypatch.setattr(release_module, "_remote_branch_exists", branch_exists)
    monkeypatch.setattr(release_module, "_publish_snapshot", publish_snapshot)

    branches = publish_release_branches(context(tmp_path), "v0.1.0", SOURCE_SHA)

    assert checked == ["rel/v0.1.0/build", "rel/v0.1.0/verification"]
    assert published == [
        ("rel/v0.1.0/build", True),
        ("rel/v0.1.0/verification", True),
    ]
    assert branches.build_branch == "rel/v0.1.0/build"
    assert branches.verification_branch == "rel/v0.1.0/verification"


def test_publish_release_branches_refuses_any_existing_release_branch(
    tmp_path: Path,
    monkeypatch,
):
    seed_release_provenance(tmp_path)
    published: list[str] = []

    monkeypatch.setattr(
        release_module,
        "_remote_branch_exists",
        lambda cwd, branch: branch.endswith("/verification"),
    )
    monkeypatch.setattr(
        release_module,
        "_publish_snapshot",
        lambda source_root, branch, message, *, immutable=False: published.append(branch),
    )

    with pytest.raises(RuntimeError, match="already exists"):
        publish_release_branches(context(tmp_path), "v0.1.0", SOURCE_SHA)

    assert published == []


def test_publish_release_branches_requires_matching_provenance(
    tmp_path: Path,
    monkeypatch,
):
    seed_release_provenance(tmp_path)
    (tmp_path / "bld" / "publication-info.txt").write_text(
        "Publication context : release\nCommit              : wrong\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(release_module, "_remote_branch_exists", lambda *args: False)

    with pytest.raises(RuntimeError, match="provenance does not match"):
        publish_release_branches(context(tmp_path), "v0.1.0", SOURCE_SHA)


def test_verification_publish_failure_rolls_back_new_build_branch(
    tmp_path: Path,
    monkeypatch,
):
    """Model a partial publish and require cleanup of the newly created build branch."""
    seed_release_provenance(tmp_path)
    calls: list[str] = []
    rollback: list[list[str]] = []

    monkeypatch.setattr(release_module, "_remote_branch_exists", lambda *args: False)

    def publish_snapshot(source_root, branch, message, *, immutable=False):
        calls.append(branch)
        if branch.endswith("/verification"):
            raise RuntimeError("verification push failed")

    monkeypatch.setattr(release_module, "_publish_snapshot", publish_snapshot)
    monkeypatch.setattr(
        release_module,
        "run_checked",
        lambda command, **kwargs: rollback.append(command),
    )

    with pytest.raises(RuntimeError, match="verification push failed"):
        publish_release_branches(context(tmp_path), "v0.1.0", SOURCE_SHA)

    assert calls == ["rel/v0.1.0/build", "rel/v0.1.0/verification"]
    assert rollback == [
        ["git", "push", "origin", "--delete", "rel/v0.1.0/build"]
    ]
