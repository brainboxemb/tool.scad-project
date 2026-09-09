"""Resolve publication policy and publish generated snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import os
from pathlib import Path
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


def _publication_config(context: ProjectContext) -> dict:
    value = context.config.get("publication", {}) or {}
    return value if isinstance(value, dict) else {}


def resolve_publication_target(
    context: ProjectContext,
    kind: str,
    environ: dict[str, str] | None = None,
) -> PublicationTarget:
    """Resolve production/development/tag/PR publication from GitHub context."""

    if kind not in {"build", "verification"}:
        raise RuntimeError(f"Unsupported publication kind: {kind}")

    env = environ or os.environ
    publication = _publication_config(context)

    production = publication.get("production", {}) or {}
    development = publication.get("development", {}) or {}
    tags = publication.get("tags", {}) or {}

    production_branch = production.get(
        f"{kind}_branch",
        publication.get(
            f"{kind}_branch",
            "build" if kind == "build" else "verification",
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
        return PublicationTarget(
            context="pull_request",
            branch=None,
            publish=False,
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
        return PublicationTarget(
            context="development",
            branch=str(development_branch),
            publish=True,
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


def publication_info_text(
    context: ProjectContext,
    kind: str,
    environ: dict[str, str] | None = None,
    runtime_info: str | None = None,
) -> str:
    """Return source, tooling and runtime provenance for generated output."""

    env = environ or os.environ
    target = resolve_publication_target(context, kind, env)

    repository = env.get("GITHUB_REPOSITORY", "unknown")
    commit = env.get("GITHUB_SHA", "unknown")
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
        ),
        encoding="utf-8",
    )
    return output


def _publish_snapshot(source_root: Path, branch: str, commit_message: str) -> None:
    """Force-replace one generated branch with source_root contents."""

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
        run_checked(
            ["git", "push", "--force", "origin", f"HEAD:{branch}"],
            cwd=snapshot,
        )


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

    if kind == "build":
        source_root = context.path(context.config["paths"]["build_root"])
        commit_message = (
            "Generated build snapshot "
            f"from {target.source_ref_type} {target.source_ref} "
            f"({os.environ.get('GITHUB_SHA', 'unknown')})"
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
            f"({os.environ.get('GITHUB_SHA', 'unknown')})"
        )

    _publish_snapshot(source_root, target.branch, commit_message)
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
