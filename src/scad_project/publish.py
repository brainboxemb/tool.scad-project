"""Resolve publication policy and publish generated snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from . import __version__
from .config import ProjectContext
from .process import run_checked


@dataclass(frozen=True)
class PublicationTarget:
    """Resolved publication destination for one generated output kind."""

    context: str
    branch: str | None
    publish: bool
    source_ref_type: str
    source_ref: str
    immutable: bool = False


def _publication_config(context: ProjectContext) -> dict:
    value = context.config.get("publication", {}) or {}
    return value if isinstance(value, dict) else {}


def _validate_kind(kind: str) -> None:
    if kind not in {"build", "verification"}:
        raise RuntimeError(f"Unsupported publication kind: {kind}")


def _pull_request_number(environ: dict[str, str]) -> int | None:
    """Return the pull-request number exposed by CI, when available."""

    explicit = environ.get("SCAD_PROJECT_PR_NUMBER", "").strip()
    if explicit:
        if not explicit.isdigit() or int(explicit) < 1:
            raise RuntimeError(
                "SCAD_PROJECT_PR_NUMBER must be a positive integer when set"
            )
        return int(explicit)

    ref_name = environ.get("GITHUB_REF_NAME", "").strip()
    match = re.fullmatch(r"([1-9][0-9]*)/merge", ref_name)
    if match:
        return int(match.group(1))

    return None


def _pull_request_branch(context: ProjectContext, kind: str, pr_number: int) -> str:
    """Return the mutable generated branch for one pull request and output kind."""

    _validate_kind(kind)
    publication = _publication_config(context)
    development = publication.get("development", {}) or {}
    prefix = str(development.get("pr_branch_prefix", "dev/pr")).strip("/")
    if not prefix:
        raise RuntimeError("publication.development.pr_branch_prefix must not be empty")
    if pr_number < 1:
        raise RuntimeError("pull-request number must be a positive integer")
    return f"{prefix}-{pr_number}/{kind}"


def pull_request_publication_branches(
    context: ProjectContext,
    pr_number: int,
) -> tuple[str, str]:
    """Return build and verification publication branches for one pull request."""

    return (
        _pull_request_branch(context, "build", pr_number),
        _pull_request_branch(context, "verification", pr_number),
    )


def resolve_release_publication_target(
    context: ProjectContext,
    kind: str,
    version: str,
) -> PublicationTarget:
    """Resolve one immutable versioned release publication destination."""

    _validate_kind(kind)
    publication = _publication_config(context)
    tags = publication.get("tags", {}) or {}
    release = publication.get("release", {}) or {}

    pattern = release.get("tag_pattern", tags.get("pattern", "v*"))
    if not version or not fnmatch(version, pattern):
        raise RuntimeError(
            f"Release version {version!r} does not match configured tag pattern {pattern!r}"
        )

    prefix = str(release.get("branch_prefix", "rel")).strip("/")
    if not prefix:
        raise RuntimeError("publication.release.branch_prefix must not be empty")

    return PublicationTarget(
        context="release",
        branch=f"{prefix}/{version}/{kind}",
        publish=True,
        source_ref_type="tag",
        source_ref=version,
        immutable=True,
    )


def resolve_publication_target(
    context: ProjectContext,
    kind: str,
    environ: dict[str, str] | None = None,
) -> PublicationTarget:
    """Resolve production/development/release/tag/PR publication context."""

    _validate_kind(kind)

    env = environ or os.environ
    publication = _publication_config(context)

    release_version = env.get("SCAD_PROJECT_RELEASE_VERSION", "").strip()
    if release_version:
        return resolve_release_publication_target(context, kind, release_version)

    production = publication.get("production", {}) or {}
    development = publication.get("development", {}) or {}
    tags = publication.get("tags", {}) or {}

    production_branch = production.get(
        f"{kind}_branch",
        publication.get(
            f"{kind}_branch",
            "prod/build" if kind == "build" else "prod/verification",
        ),
    )
    development_branch = development.get(
        f"{kind}_branch",
        "dev/build" if kind == "build" else "dev/verification",
    )
    production_source = production.get("source_branch", "main")

    event_name = env.get("GITHUB_EVENT_NAME", "")
    ref_type = env.get("GITHUB_REF_TYPE", "")
    ref_name = env.get("GITHUB_REF_NAME", "")

    if event_name == "pull_request":
        source_ref = env.get("GITHUB_HEAD_REF") or ref_name or "pull-request"
        pr_number = _pull_request_number(env)
        if pr_number is None:
            return PublicationTarget(
                context="pull_request",
                branch=None,
                publish=False,
                source_ref_type="pull_request",
                source_ref=source_ref,
            )
        return PublicationTarget(
            context="pull_request",
            branch=_pull_request_branch(context, kind, pr_number),
            publish=True,
            source_ref_type="pull_request",
            source_ref=source_ref,
        )

    if ref_type == "tag":
        pattern = tags.get("pattern", "v*")
        source_ref = ref_name or env.get("GITHUB_REF", "tag")
        tag_context = "tag" if fnmatch(source_ref, pattern) else "tag-unmatched"
        return PublicationTarget(
            context=tag_context,
            branch=None,
            publish=False,
            source_ref_type="tag",
            source_ref=source_ref,
        )

    if ref_type == "branch":
        source_ref = ref_name or env.get("GITHUB_REF", "branch")
        if source_ref == production_source:
            return PublicationTarget(
                context="production",
                branch=str(production_branch),
                publish=True,
                source_ref_type="branch",
                source_ref=source_ref,
            )

        # Development publication belongs to the pull request so parallel work cannot
        # race on one shared dev/build or dev/verification branch. Projects can opt in
        # to the legacy shared branch while migrating.
        if bool(development.get("publish_branch_pushes", False)):
            return PublicationTarget(
                context="development",
                branch=str(development_branch),
                publish=True,
                source_ref_type="branch",
                source_ref=source_ref,
            )
        return PublicationTarget(
            context="development",
            branch=None,
            publish=False,
            source_ref_type="branch",
            source_ref=source_ref,
        )

    return PublicationTarget(
        context="local",
        branch=None,
        publish=False,
        source_ref_type=ref_type or "unknown",
        source_ref=ref_name or "unknown",
    )


def _runtime_component_info() -> str | None:
    """Return scad-toolchain-info output when the runtime exposes it."""

    command = shutil.which("scad-toolchain-info")
    if not command:
        return None

    completed = subprocess.run(
        [command],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return f"scad-toolchain-info failed (exit {completed.returncode})"

    output = completed.stdout.strip()
    return output or None


def _submodule_info(root: Path) -> str | None:
    """Return deterministic path/SHA provenance for checked-out git submodules."""

    command = shutil.which("git")
    if not command:
        return None

    completed = subprocess.run(
        [command, "-C", str(root), "submodule", "status", "--recursive"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return f"git submodule status failed (exit {completed.returncode})"

    entries: list[str] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line[0] in "+-U":
            line = line[1:].lstrip()
        parts = line.split()
        if len(parts) >= 2:
            entries.append(f"{parts[1]} : {parts[0]}")

    return "\n".join(sorted(entries)) or None


def publication_info_text(
    context: ProjectContext,
    kind: str,
    environ: dict[str, str] | None = None,
    runtime_info: str | None = None,
    submodule_info: str | None = None,
) -> str:
    """Return source, tooling and runtime provenance for generated output."""

    env = environ or os.environ
    target = resolve_publication_target(context, kind, env)

    repository = env.get("GITHUB_REPOSITORY", "unknown")
    commit = env.get("SCAD_PROJECT_SOURCE_SHA", env.get("GITHUB_SHA", "unknown"))
    actor = env.get("GITHUB_ACTOR", "unknown")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    run_id = env.get("GITHUB_RUN_ID", "")
    workflow_run = (
        f"{server}/{repository}/actions/runs/{run_id}"
        if repository != "unknown" and run_id
        else "unknown"
    )

    toolchain_image = env.get("SCAD_TOOLCHAIN_IMAGE", "unknown")
    toolchain_version = env.get("SCAD_TOOLCHAIN_VERSION", "unknown")
    tool_version = env.get(
        "SCAD_PROJECT_WORKFLOW_VERSION",
        f"v{__version__}",
    )

    lines = [
        f"Publication context : {target.context}",
        f"Publication kind    : {kind}",
        f"Publication branch  : {target.branch or '(artifact only)'}",
        "",
        "Source",
        "------",
        f"Repository          : {repository}",
        f"Ref type            : {target.source_ref_type}",
        f"Ref                 : {target.source_ref}",
        f"Commit              : {commit}",
        f"Triggered by        : {actor}",
        f"Workflow run        : {workflow_run}",
        "",
        "Tooling",
        "-------",
        f"SCAD toolchain image: {toolchain_image}",
        f"SCAD toolchain ver. : {toolchain_version}",
        f"tool.scad-project   : {tool_version}",
    ]

    if submodule_info:
        lines.extend([
            "",
            "Git submodules",
            "--------------",
            submodule_info.rstrip(),
        ])

    if runtime_info:
        lines.extend([
            "",
            "Runtime components",
            "------------------",
            runtime_info.rstrip(),
        ])

    return "\n".join(lines) + "\n"


def write_publication_info(context: ProjectContext, kind: str) -> Path:
    """Write publication-info.txt into the generated output root."""

    if kind == "build":
        root = context.path(context.config["paths"]["build_root"])
    elif kind == "verification":
        verification = context.config.get("verification", {}) or {}
        output_root = verification.get("output_root")
        if not output_root:
            raise RuntimeError(
                "verification.output_root is required for publication info"
            )
        root = context.path(output_root)
    else:
        raise RuntimeError(f"Unsupported publication kind: {kind}")

    root.mkdir(parents=True, exist_ok=True)
    output = root / "publication-info.txt"
    output.write_text(
        publication_info_text(
            context,
            kind,
            runtime_info=_runtime_component_info(),
            submodule_info=_submodule_info(context.root),
        ),
        encoding="utf-8",
    )
    return output


def _remote_branch_exists(cwd: Path, branch: str) -> bool:
    completed = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Could not check whether publication branch exists: {branch}"
        )
    return bool(completed.stdout.strip())


def cleanup_pull_request_publication(
    context: ProjectContext,
    pr_number: int,
) -> tuple[str, ...]:
    """Delete mutable generated publication branches for one closed pull request."""

    branches = pull_request_publication_branches(context, pr_number)
    removed: list[str] = []
    for branch in branches:
        if not _remote_branch_exists(context.root, branch):
            continue
        run_checked(
            ["git", "push", "origin", "--delete", branch],
            cwd=context.root,
        )
        removed.append(branch)
    return tuple(removed)


def _publish_snapshot(
    source_root: Path,
    branch: str,
    commit_message: str,
    *,
    immutable: bool = False,
) -> None:
    """Publish one generated branch, replacing only mutable destinations."""

    if not source_root.exists() or not any(source_root.iterdir()):
        raise RuntimeError(f"Generated output directory is empty: {source_root}")

    repository = os.environ.get("GITHUB_REPOSITORY")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    if not repository:
        raise RuntimeError(
            "GITHUB_REPOSITORY is required for publication. "
            "Use this command from CI or provide an authenticated Git remote workflow."
        )

    with tempfile.TemporaryDirectory(prefix="scad-project-publish-") as td:
        snapshot = Path(td)
        for item in source_root.iterdir():
            dest = snapshot / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        run_checked(["git", "init", "-q"], cwd=snapshot)
        run_checked(["git", "checkout", "--orphan", "snapshot"], cwd=snapshot)
        run_checked(["git", "config", "user.name", "github-actions[bot]"], cwd=snapshot)
        run_checked(
            [
                "git", "config", "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            cwd=snapshot,
        )
        run_checked(["git", "add", "."], cwd=snapshot)
        run_checked(["git", "commit", "-q", "-m", commit_message], cwd=snapshot)
        run_checked(
            ["git", "remote", "add", "origin", f"{server}/{repository}.git"],
            cwd=snapshot,
        )

        if immutable and _remote_branch_exists(snapshot, branch):
            raise RuntimeError(
                f"Immutable release publication branch already exists: {branch}"
            )

        push = ["git", "push"]
        if not immutable:
            push.append("--force")
        push.extend(["origin", f"HEAD:{branch}"])
        run_checked(push, cwd=snapshot)


def _publish(context: ProjectContext, kind: str) -> None:
    target = resolve_publication_target(context, kind)
    info = write_publication_info(context, kind)

    if not target.publish or not target.branch:
        print(
            f"{kind}: artifact-only publication context "
            f"({target.context}, {target.source_ref_type} {target.source_ref})"
        )
        print(f"Publication provenance: {info}")
        return

    source_commit = os.environ.get(
        "SCAD_PROJECT_SOURCE_SHA",
        os.environ.get("GITHUB_SHA", "unknown"),
    )

    if kind == "build":
        source_root = context.path(context.config["paths"]["build_root"])
        commit_message = (
            "Generated build snapshot "
            f"from {target.source_ref_type} {target.source_ref} "
            f"({source_commit})"
        )
    else:
        verification = context.config.get("verification", {}) or {}
        output_root = verification.get("output_root")
        if not output_root:
            raise RuntimeError(
                "verification.output_root is required for publish-verification"
            )
        source_root = context.path(output_root)
        commit_message = (
            "Generated verification snapshot "
            f"from {target.source_ref_type} {target.source_ref} "
            f"({source_commit})"
        )

    _publish_snapshot(
        source_root,
        target.branch,
        commit_message,
        immutable=target.immutable,
    )
    print(
        f"Published generated {kind} to branch: {target.branch} "
        f"({target.context} from {target.source_ref})"
    )


def publish_build(context: ProjectContext) -> None:
    """Publish build output according to the resolved publication policy."""

    _publish(context, "build")


def publish_verification(context: ProjectContext) -> None:
    """Publish verification evidence according to the resolved policy."""

    _publish(context, "verification")
