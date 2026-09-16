"""Persistent producer execution evidence for SCAD domain actions.

The generic schema is owned by tool.git-project. This module supplies the
SCAD-specific producer-side values and keeps richer SCons decision telemetry as
separate domain evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

from . import __version__
from .config import ProjectContext


SCHEMA_NAME = "brainboxemb.execution-evidence"
SCHEMA_VERSION = 1
OWNER = "brainboxemb/tool.scad-project"
_REVISION_RE = re.compile(r"^[0-9A-Fa-f]{40,64}$")
_NAVIGATION_MARKER = "<!-- scad-project-evidence-navigation -->"
_TIMING_PHASE_LABELS = {
    "preflight_and_plan": "Preflight + execution plan",
    "cache_restore": "Cache restore",
    "runtime_pull": "Runtime pull",
    "materialization": "Capability materialization",
    "cache_save": "Cache save",
    "finishing": "Validation + finishing",
    "snapshot_preparation": "Snapshot preparation",
    "publication": "Generated-output publication",
}


def _git_head(path: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value if _REVISION_RE.fullmatch(value) else None


def _source_revision(context: ProjectContext) -> str:
    explicit = os.environ.get("SCAD_PROJECT_SOURCE_SHA", "").strip()
    if _REVISION_RE.fullmatch(explicit):
        return explicit
    value = _git_head(context.root)
    if value:
        return value
    raise RuntimeError("could not resolve exact producer source revision")


def _owner_revision(context: ProjectContext) -> str:
    explicit = os.environ.get("SCAD_PROJECT_TOOL_SHA", "").strip()
    if _REVISION_RE.fullmatch(explicit):
        return explicit

    tooling = context.config.get("tooling", {}) or {}
    tool = tooling.get("tool_scad_project")
    tool_path = (
        str(tool.get("path", "tools/tool.scad-project"))
        if isinstance(tool, dict)
        else "tools/tool.scad-project"
    )
    for candidate in (
        context.path(tool_path),
        Path(__file__).resolve().parents[2],
    ):
        value = _git_head(candidate)
        if value:
            return value
    raise RuntimeError("could not resolve exact tool.scad-project owner revision")


def _relative(from_dir: Path, target: Path) -> str:
    return os.path.relpath(target, from_dir).replace(os.sep, "/")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _producer_timing() -> dict[str, Any] | None:
    """Return timing started by the shared Moon producer wrapper when available."""

    started_at = os.environ.get("SCAD_PROJECT_PRODUCER_STARTED_AT", "").strip()
    raw_started_ns = os.environ.get(
        "SCAD_PROJECT_PRODUCER_STARTED_MONOTONIC_NS",
        "",
    ).strip()
    if not started_at or not raw_started_ns:
        return None
    try:
        started_ns = int(raw_started_ns)
    except ValueError:
        return None

    duration_ms = max(0, (time.monotonic_ns() - started_ns) // 1_000_000)
    return {
        "started_at": started_at,
        "finished_at": _utc_now(),
        "duration_ms": duration_ms,
    }


def _decision_summary(report: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    kind = report.get("kind")
    engine = report.get("engine")
    target_count = report.get("target_count")
    if kind:
        lines.append(f"Decision report kind: {kind}")
    if engine:
        lines.append(f"Build engine: {engine}")
    if isinstance(target_count, int):
        lines.append(f"Targets: {target_count}")

    counts = report.get("outcome_counts")
    if isinstance(counts, dict):
        ordered = ("BUILT", "CACHE_RESTORED", "CURRENT", "ERROR")
        summary = ", ".join(
            f"{name}={int(counts.get(name, 0))}" for name in ordered
        )
        lines.append(f"Outcomes: {summary}")

    targets = report.get("targets")
    if isinstance(targets, list) and targets:
        lines.extend(["", "Target decisions:"])
        for target in targets:
            if not isinstance(target, dict):
                continue
            output = target.get("output", "unknown")
            outcome = target.get("outcome", "unknown")
            lines.append(f"- {outcome}: {output}")
    return lines


def write_execution_evidence(
    context: ProjectContext,
    *,
    capability: str,
    action: str,
    execution_id: str,
    output_root: Path,
    domain_report: Path | None = None,
) -> Path | None:
    """Write one common execution envelope plus one concise SCAD producer log.

    Local/unit use outside a resolvable Git checkout remains supported. In that
    case the producer action succeeds but persistent execution evidence is skipped
    with a warning. Persistent CI/publication consumers must assert the evidence
    files and schema explicitly, so a published snapshot cannot silently qualify
    without exact source and owner revisions.
    """

    try:
        source_revision = _source_revision(context)
        owner_revision = _owner_revision(context)
    except RuntimeError as exc:
        print(f"WARNING: persistent SCAD execution evidence skipped: {exc}")
        return None

    evidence_root = output_root / "evidence"
    execution_root = evidence_root / "executions" / execution_id
    domain_root = evidence_root / "domain"
    execution_root.mkdir(parents=True, exist_ok=True)

    domain_paths: list[str] = []
    report_payload: dict[str, Any] | None = None
    if domain_report is not None and domain_report.is_file():
        domain_root.mkdir(parents=True, exist_ok=True)
        copied_report = domain_root / domain_report.name
        shutil.copy2(domain_report, copied_report)
        domain_paths.append(_relative(execution_root, copied_report))
        try:
            value = json.loads(copied_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Could not read SCAD domain evidence: {copied_report}"
            ) from exc
        if isinstance(value, dict):
            report_payload = value

    producer_timing = _producer_timing()
    log_lines = [
        "SCAD producer execution",
        "=======================",
        "",
        f"Capability: {capability}",
        f"Action: {action}",
        f"Source revision: {source_revision}",
        f"Owner: {OWNER}",
        f"Owner revision: {owner_revision}",
        f"tool.scad-project version: {__version__}",
        "Status: success",
    ]
    if producer_timing is not None:
        log_lines.extend(
            [
                f"Producer started (UTC): {producer_timing['started_at']}",
                f"Producer finished (UTC): {producer_timing['finished_at']}",
                f"Producer duration: {producer_timing['duration_ms']} ms",
            ]
        )
    if domain_paths:
        log_lines.extend(["", f"Domain evidence: {domain_paths[0]}"])
    else:
        log_lines.extend([
            "",
            "Domain evidence: no structured SCons decision report for this execution.",
        ])
    if report_payload is not None:
        summary = _decision_summary(report_payload)
        if summary:
            log_lines.extend(["", *summary])

    log_path = execution_root / "execution.log"
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    payload: dict[str, Any] = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "capability": capability,
        "owner": OWNER,
        "action": action,
        "source_revision": source_revision,
        "owner_revision": owner_revision,
        "status": "success",
        "exit_code": 0,
        "log": "execution.log",
        "domain_evidence": domain_paths,
        "tool_scad_project_version": __version__,
    }
    if producer_timing is not None:
        payload["producer_execution"] = producer_timing

    output = execution_root / "execution.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _format_duration(duration: Any) -> str:
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
        return "unknown"
    if duration < 1000:
        return f"{duration} ms"
    return f"{duration / 1000:.3f} s"


def _workflow_timing_table(output_root: Path, timings: Path) -> list[str]:
    try:
        payload = json.loads(timings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    phases = payload.get("phases")
    if not isinstance(phases, list) or not phases:
        return []

    lines = [
        "",
        "### Current workflow timing",
        "",
        "| Phase | Duration |",
        "| --- | ---: |",
    ]
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        name = str(phase.get("name", "unknown"))
        label = _TIMING_PHASE_LABELS.get(name, name.replace("_", " ").title())
        lines.append(f"| {label} | {_format_duration(phase.get('duration_ms'))} |")
    if "total_to_snapshot_ms" in payload:
        lines.append(
            f"| **Total to prepared snapshot** | **{_format_duration(payload.get('total_to_snapshot_ms'))}** |"
        )
    lines.extend(
        [
            "",
            "The table stops when this generated snapshot is ready. The remote branch push happens afterwards; detailed per-capability timings remain in the materialization files below.",
            "",
        ]
    )
    return lines


def _orchestration_navigation_lines(output_root: Path) -> list[str]:
    orchestration_root = output_root / "orchestration"
    lines = [
        "## Orchestration/materialization evidence",
        "",
        "Current-run orchestration evidence explains why capabilities were selected, whether Moon executed or hydrated them, and how long current materialization and snapshot preparation took.",
        "Producer execution evidence above remains the authority for the work that originally created cached output.",
        "",
    ]

    if not orchestration_root.is_dir():
        lines.extend(
            [
                "- Current orchestration evidence is attached by the publication layer.",
                "- A later cache hydration may therefore have a current materialization revision that differs from the retained producer `source_revision`.",
                "",
            ]
        )
        return lines

    known = (
        ("timings.json", "Workflow phase timings"),
        ("run-context.json", "Run context and snapshot-preparation timing"),
        ("impact-decision.json", "Moon impact decision"),
        ("affected-task-ids.json", "Affected Moon task ids"),
        ("scad-ci-plan.json", "SCAD execution/materialization plan"),
    )
    for name, label in known:
        path = orchestration_root / name
        if path.is_file():
            lines.append(f"- [{label}]({_relative(output_root, path)})")

    timings = orchestration_root / "timings.json"
    if timings.is_file():
        lines.extend(_workflow_timing_table(output_root, timings))

    invocation_root = orchestration_root / "moon-invocations"
    if invocation_root.is_dir():
        for invocation in sorted(path for path in invocation_root.iterdir() if path.is_dir()):
            task = invocation.name.replace("consumer_", "consumer:", 1)
            materialization = invocation / "materialization.json"
            moon_log = invocation / "moon.log"
            if materialization.is_file():
                lines.append(
                    f"- [{task} materialization]({_relative(output_root, materialization)}) — current execute/cache/hydrate result and duration."
                )
            if moon_log.is_file():
                lines.append(
                    f"  - [{task} raw Moon/producer log]({_relative(output_root, moon_log)})"
                )

    lines.append("")
    return lines


def evidence_navigation_lines(
    output_root: Path,
    *,
    include_publication_context: bool = True,
) -> list[str]:
    """Return human-facing navigation for retained evidence in one output root."""

    execution_root = output_root / "evidence" / "executions"
    domain_root = output_root / "evidence" / "domain"
    executions = sorted(execution_root.glob("*/execution.json")) if execution_root.exists() else []
    reports = sorted(domain_root.glob("*.json")) if domain_root.exists() else []

    lines = [
        _NAVIGATION_MARKER,
        "## Producer execution evidence",
        "",
        "These files describe the SCAD producer executions that actually created the retained output.",
        "They remain unchanged when equivalent output is later hydrated from cache.",
        "",
    ]
    if executions:
        for execution in executions:
            execution_id = execution.parent.name
            log = execution.parent / "execution.log"
            lines.append(
                f"- [{execution_id} execution]({_relative(output_root, execution)}) — "
                "capability, producer source revision, exact owner revision, result and producer timing when available."
            )
            if log.is_file():
                lines.append(
                    f"  - [{execution_id} log]({_relative(output_root, log)}) — concise human-readable producer summary."
                )
    else:
        lines.append("- No producer execution evidence is present.")

    lines.extend([
        "",
        "## Domain evidence",
        "",
        "Structured SCAD/SCons reports contain the detailed target-level build and cache decisions.",
        "They are richer domain evidence, not alternate producer logs.",
        "",
    ])
    if reports:
        for report in reports:
            lines.append(f"- [{report.name}]({_relative(output_root, report)})")
    else:
        lines.append("- No structured domain reports are present for this output.")

    lines.extend(["", *_orchestration_navigation_lines(output_root)])
    if include_publication_context:
        lines.extend([
            "## Publication context",
            "",
            "`publication-info.txt` records generated-branch context plus source, tooling and runtime provenance.",
            "Publication/finalization consumes prepared output and must not rewrite producer execution evidence.",
            "",
        ])
    return lines


def append_evidence_navigation(readme: Path, output_root: Path) -> None:
    """Append the standard evidence map to an existing generated README once."""

    if not readme.is_file():
        return
    text = readme.read_text(encoding="utf-8").rstrip()
    if _NAVIGATION_MARKER in text:
        text = text.split(_NAVIGATION_MARKER, 1)[0].rstrip()
    navigation = "\n".join(evidence_navigation_lines(output_root)).rstrip()
    readme.write_text(f"{text}\n\n{navigation}\n", encoding="utf-8")
