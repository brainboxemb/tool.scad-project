"""Create downloadable bundles and finalize versioned release branches."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import zipfile

from .config import ProjectContext
from .process import run_checked
from .publish import (
    _publish_snapshot,
    _remote_branch_exists,
    resolve_release_publication_target,
)


_NORMALIZED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_SAFE_ASSET_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class ReleaseArtifacts:
    """Paths generated for one versioned release package set."""

    version: str
    output_dir: Path
    build_bundle: Path
    verification_bundle: Path
    stl_bundle: Path | None
    checksums: Path

    @property
    def assets(self) -> tuple[Path, ...]:
        values: list[Path] = [self.build_bundle, self.verification_bundle]
        if self.stl_bundle is not None:
            values.append(self.stl_bundle)
        values.append(self.checksums)
        return tuple(values)


@dataclass(frozen=True)
class ReleaseBranches:
    """Immutable browseable branches created for one project release."""

    version: str
    build_branch: str
    verification_branch: str


def _safe_asset_component(value: str) -> str:
    safe = _SAFE_ASSET_RE.sub("-", value.strip()).strip("-.")
    if not safe:
        raise RuntimeError(f"Could not derive a safe release asset name from {value!r}")
    return safe


def release_asset_prefix(context: ProjectContext, version: str) -> str:
    """Return the shared, filesystem-safe prefix for downloadable assets."""

    resolve_release_publication_target(context, "build", version)
    project = context.config.get("project", {}) or {}
    name = project.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError("project.name is required for release packaging")
    return f"{_safe_asset_component(name)}-{_safe_asset_component(version)}"


def _archive_files(root: Path, *, suffix: str | None = None) -> list[Path]:
    if not root.is_dir():
        raise RuntimeError(f"Release input directory does not exist: {root}")

    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Release bundles do not support symlinks: {path}")
        if not path.is_file():
            continue
        if suffix is not None and path.suffix.lower() != suffix.lower():
            continue
        files.append(path)

    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _write_deterministic_zip(
    root: Path,
    output: Path,
    *,
    suffix: str | None = None,
    required: bool = True,
) -> bool:
    files = _archive_files(root, suffix=suffix)
    if not files:
        if required:
            raise RuntimeError(f"Release input contains no files: {root}")
        return False

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=_NORMALIZED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _output_roots(context: ProjectContext) -> tuple[Path, Path]:
    build_root = context.path(context.config["paths"]["build_root"])
    verification = context.config.get("verification", {}) or {}
    verification_root_value = verification.get("output_root")
    if not verification_root_value:
        raise RuntimeError("verification.output_root is required for release publication")
    return build_root, context.path(verification_root_value)


def package_release(
    context: ProjectContext,
    version: str,
    output_dir: Path | None = None,
) -> ReleaseArtifacts:
    """Package build/verification output and write SHA256SUMS.txt."""

    prefix = release_asset_prefix(context, version)
    build_root, verification_root = _output_roots(context)

    release_dir = (
        output_dir
        if output_dir is not None
        else context.root / ".cache" / "scad-project" / "release" / version
    )
    if not release_dir.is_absolute():
        release_dir = context.root / release_dir
    release_dir.mkdir(parents=True, exist_ok=True)

    build_bundle = release_dir / f"{prefix}-build.zip"
    verification_bundle = release_dir / f"{prefix}-verification.zip"
    stl_bundle = release_dir / f"{prefix}-stl.zip"

    _write_deterministic_zip(build_root, build_bundle)
    _write_deterministic_zip(verification_root, verification_bundle)

    stl_root = build_root / "stl"
    has_stl = (
        stl_root.is_dir()
        and _write_deterministic_zip(
            stl_root,
            stl_bundle,
            suffix=".stl",
            required=False,
        )
    )
    resolved_stl = stl_bundle if has_stl else None

    downloadable: list[Path] = [build_bundle, verification_bundle]
    if resolved_stl is not None:
        downloadable.append(resolved_stl)

    checksums = release_dir / "SHA256SUMS.txt"
    checksums.write_text(
        "".join(
            f"{_sha256(path)}  {path.name}\n"
            for path in sorted(downloadable, key=lambda item: item.name)
        ),
        encoding="utf-8",
    )

    return ReleaseArtifacts(
        version=version,
        output_dir=release_dir,
        build_bundle=build_bundle,
        verification_bundle=verification_bundle,
        stl_bundle=resolved_stl,
        checksums=checksums,
    )


def release_branches(context: ProjectContext, version: str) -> ReleaseBranches:
    """Resolve both immutable browseable branch names for a release."""

    build = resolve_release_publication_target(context, "build", version)
    verification = resolve_release_publication_target(context, "verification", version)
    assert build.branch is not None
    assert verification.branch is not None
    return ReleaseBranches(
        version=version,
        build_branch=build.branch,
        verification_branch=verification.branch,
    )


def _require_release_provenance(
    root: Path,
    *,
    version: str,
    branch: str,
    source_sha: str,
) -> None:
    info = root / "publication-info.txt"
    if not info.is_file():
        raise RuntimeError(f"Release artifact is missing publication provenance: {info}")

    text = info.read_text(encoding="utf-8")
    required = (
        "Publication context : release",
        f"Publication branch  : {branch}",
        "Ref type            : tag",
        f"Ref                 : {version}",
        f"Commit              : {source_sha}",
    )
    missing = [line for line in required if line not in text]
    if missing:
        raise RuntimeError(
            f"Release artifact provenance does not match {version} @ {source_sha}: "
            + "; ".join(missing)
        )


def publish_release_branches(
    context: ProjectContext,
    version: str,
    source_sha: str,
) -> ReleaseBranches:
    """Publish build and verification snapshots only after coordinated preflight."""

    if not _SHA_RE.fullmatch(source_sha):
        raise RuntimeError("release source SHA must be an exact 40-character commit SHA")

    branches = release_branches(context, version)
    build_root, verification_root = _output_roots(context)

    for branch in (branches.build_branch, branches.verification_branch):
        if _remote_branch_exists(context.root, branch):
            raise RuntimeError(
                f"Immutable release publication branch already exists: {branch}"
            )

    _require_release_provenance(
        build_root,
        version=version,
        branch=branches.build_branch,
        source_sha=source_sha,
    )
    _require_release_provenance(
        verification_root,
        version=version,
        branch=branches.verification_branch,
        source_sha=source_sha,
    )

    build_message = f"Generated build release {version} ({source_sha})"
    verification_message = f"Generated verification release {version} ({source_sha})"

    _publish_snapshot(
        build_root,
        branches.build_branch,
        build_message,
        immutable=True,
    )
    try:
        _publish_snapshot(
            verification_root,
            branches.verification_branch,
            verification_message,
            immutable=True,
        )
    except Exception as exc:
        try:
            run_checked(
                ["git", "push", "origin", "--delete", branches.build_branch],
                cwd=context.root,
            )
        except Exception as rollback_exc:
            raise RuntimeError(
                f"Verification release publication failed and build-branch rollback "
                f"also failed: {rollback_exc}"
            ) from exc
        raise

    return branches
