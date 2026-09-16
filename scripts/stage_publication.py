#!/usr/bin/env python3
"""Stage one generated publication family with current orchestration evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time

from scad_project.execution_evidence import append_evidence_navigation
from scad_project.workflow_timing import snapshot_timings


SCHEMA = "brainboxemb.scad-orchestration-run-context"
SCHEMA_VERSION = 1


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _copy_required(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"required orchestration evidence is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def stage_publication(
    *,
    source_root: Path,
    staging_root: Path,
    family: str,
    source_sha: str,
    base_sha: str,
    workspace: Path,
) -> Path:
    """Copy prepared output and attach current-run orchestration evidence."""

    started_at = _utc_now()
    started_ns = time.monotonic_ns()

    if family not in {"build", "verification"}:
        raise RuntimeError(f"unsupported publication family: {family}")
    if not source_root.is_dir() or not any(source_root.iterdir()):
        raise RuntimeError(f"publication source is empty or missing: {source_root}")

    if staging_root.exists():
        shutil.rmtree(staging_root)
    shutil.copytree(source_root, staging_root)

    orchestration = staging_root / "orchestration"
    orchestration.mkdir(parents=True, exist_ok=True)
    preflight = workspace / ".moon" / "preflight"
    invocations = workspace / ".moon" / "invocations"

    _copy_required(
        preflight / "decision.json",
        orchestration / "impact-decision.json",
    )
    _copy_required(
        preflight / "affected-task-ids.json",
        orchestration / "affected-task-ids.json",
    )
    _copy_required(
        preflight / "scad-ci-plan.json",
        orchestration / "scad-ci-plan.json",
    )
    timing_source = preflight / "workflow-timings.json"
    if not timing_source.is_file():
        raise RuntimeError(f"current workflow timing evidence is missing: {timing_source}")
    if not invocations.is_dir():
        raise RuntimeError(f"current Moon invocation evidence is missing: {invocations}")
    shutil.copytree(
        invocations,
        orchestration / "moon-invocations",
        dirs_exist_ok=True,
    )

    finished_at = _utc_now()
    duration_ms = max(0, (time.monotonic_ns() - started_ns) // 1_000_000)

    run_context_path = orchestration / "run-context.json"
    run_context = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "publication_family": family,
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        "source_revision": source_sha,
        "base_revision": base_sha,
        "snapshot_preparation": {
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
        },
    }
    run_context_path.write_text(
        json.dumps(run_context, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    timing_path = orchestration / "timings.json"
    timing_path.write_text(
        json.dumps(
            snapshot_timings(
                timing_source,
                publication_family=family,
                snapshot_started_at=started_at,
                snapshot_finished_at=finished_at,
                snapshot_duration_ms=duration_ms,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    append_evidence_navigation(staging_root / "README.md", staging_root)
    return run_context_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--staging-root", required=True, type=Path)
    parser.add_argument("--family", required=True, choices=("build", "verification"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    return parser


def main() -> None:
    args = _parser().parse_args()
    output = stage_publication(
        source_root=args.source_root,
        staging_root=args.staging_root,
        family=args.family,
        source_sha=args.source_sha,
        base_sha=args.base_sha,
        workspace=args.workspace,
    )
    print(f"orchestration run context: {output}")


if __name__ == "__main__":
    main()
