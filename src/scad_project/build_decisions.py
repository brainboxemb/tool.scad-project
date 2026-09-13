"""Structured, shared build-decision telemetry for selective SCons targets."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import __version__


REPORT_SCHEMA = "scad-project.build-decisions"
REPORT_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
OUTCOMES = ("BUILT", "CACHE_RESTORED", "CURRENT", "ERROR")


def target_spec_digest(spec: dict[str, Any]) -> str:
    """Return a stable digest for the target specification."""

    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def capture_output_state(project_root: Path, targets: list[dict[str, Any]]) -> None:
    """Record output existence immediately before SCons starts."""

    root = project_root.resolve()
    for spec in targets:
        output = Path(str(spec["output"]))
        if not output.is_absolute():
            output = root / output
        spec["existed_before"] = output.exists()


def classify_outcome(*, executed: bool, existed_before: bool, exists_after: bool) -> str:
    """Classify one target from action execution and pre/post output state."""

    if executed and exists_after:
        return "BUILT"
    if not executed and not existed_before and exists_after:
        return "CACHE_RESTORED"
    if not executed and existed_before and exists_after:
        return "CURRENT"
    return "ERROR"


def _optional_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() == "true"


def _environment_provenance() -> dict[str, Any]:
    return {
        "source_commit_sha": os.environ.get("SCAD_PROJECT_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
        "tool_version": __version__,
        "tool_commit_sha": os.environ.get("SCAD_PROJECT_TOOL_SHA"),
        "toolchain_image": os.environ.get("SCAD_TOOLCHAIN_IMAGE"),
        "toolchain_version": os.environ.get("SCAD_TOOLCHAIN_VERSION"),
        "workflow_version": os.environ.get("SCAD_PROJECT_WORKFLOW_VERSION"),
        "cache": {
            "namespace": os.environ.get("SCAD_PROJECT_CACHE_NAMESPACE"),
            "primary_key": os.environ.get("SCAD_PROJECT_CACHE_PRIMARY_KEY"),
            "matched_key": os.environ.get("SCAD_PROJECT_CACHE_MATCHED_KEY"),
            "exact_hit": _optional_bool(os.environ.get("SCAD_PROJECT_CACHE_HIT")),
        },
    }


def write_decision_report(
    *,
    project_root: Path,
    manifest: Path,
    report_path: Path,
    report_kind: str,
    backend_signature: str | None = None,
) -> dict[str, Any]:
    """Write one compatible per-target outcome report from an SCons manifest."""

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    execution_log = Path(payload["execution_log"])
    executed = (
        execution_log.read_text(encoding="utf-8").splitlines()
        if execution_log.is_file()
        else []
    )
    executed_set = set(executed)
    root = project_root.resolve()

    target_reports: list[dict[str, Any]] = []
    for spec in payload["targets"]:
        output_value = str(spec["output"])
        output_path = Path(output_value)
        if not output_path.is_absolute():
            output_path = root / output_path
        exists_after = output_path.exists()
        existed_before = bool(spec.get("existed_before", False))
        was_executed = output_value in executed_set
        outcome = classify_outcome(
            executed=was_executed,
            existed_before=existed_before,
            exists_after=exists_after,
        )
        sources = spec.get("sources", spec.get("dependencies", []))
        if not sources and spec.get("source"):
            sources = [spec["source"]]

        digest_source = {
            key: value
            for key, value in spec.items()
            if key != "existed_before"
        }
        target_reports.append(
            {
                "output": output_value,
                "outcome": outcome,
                "action_executed": was_executed,
                "existed_before": existed_before,
                "exists_after": exists_after,
                "sources": [str(value) for value in sources],
                "target_spec_digest": target_spec_digest(digest_source),
            }
        )

    counts = Counter(target["outcome"] for target in target_reports)
    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "manifest_schema_version": payload.get("schema_version"),
        "kind": report_kind,
        "engine": "scons",
        "backend_signature": backend_signature,
        "provenance": _environment_provenance(),
        "target_count": len(target_reports),
        "outcome_counts": {outcome: counts.get(outcome, 0) for outcome in OUTCOMES},
        "targets": target_reports,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def print_decision_summary(label: str, report: dict[str, Any]) -> None:
    """Print a concise human summary using the same structured outcome vocabulary."""

    counts = report["outcome_counts"]
    print(
        f"{label}: targets={report['target_count']} "
        f"built={counts['BUILT']} cache-restored={counts['CACHE_RESTORED']} "
        f"current={counts['CURRENT']} error={counts['ERROR']}"
    )
    for target in report["targets"]:
        print(f"  {target['outcome'].lower()}: {target['output']}")
