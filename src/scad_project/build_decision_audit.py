"""Post-build audit policy for structured SCAD build-decision reports."""

from __future__ import annotations

from collections import Counter
import json
import posixpath
from pathlib import Path
from typing import Any, Iterable

from . import build_decisions


AUDIT_SCHEMA = "scad-project.build-decision-audit"
AUDIT_SCHEMA_VERSION = 1
AUDIT_RESULTS = ("PASS", "WARNING", "FAIL")
IMPACTS = ("PROVEN", "NO_PROVEN_IMPACT")


class BuildDecisionAuditError(RuntimeError):
    """Raised when build-decision audit input is malformed or unsupported."""


def normalize_path(value: str) -> str:
    """Normalize one path for exact repository-style comparison."""

    if not isinstance(value, str) or not value.strip():
        raise BuildDecisionAuditError("changed/source paths must be non-empty strings")
    normalized = posixpath.normpath(value.strip().replace("\\", "/"))
    if normalized in {"", "."}:
        raise BuildDecisionAuditError(f"invalid audit path: {value!r}")
    return normalized


def normalize_changed_paths(values: Iterable[str]) -> list[str]:
    """Return deterministic de-duplicated changed paths."""

    return sorted({normalize_path(value) for value in values})


def _validated_targets(report: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        raise BuildDecisionAuditError("decision report must be a JSON object")
    if report.get("schema") != build_decisions.REPORT_SCHEMA:
        raise BuildDecisionAuditError(
            f"unsupported decision-report schema: {report.get('schema')!r}"
        )
    if report.get("schema_version") != build_decisions.REPORT_SCHEMA_VERSION:
        raise BuildDecisionAuditError(
            "unsupported decision-report schema_version: "
            f"{report.get('schema_version')!r}"
        )

    targets = report.get("targets")
    if not isinstance(targets, list):
        raise BuildDecisionAuditError("decision report targets must be a list")

    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise BuildDecisionAuditError(f"target {index} must be an object")
        output = target.get("output")
        if not isinstance(output, str) or not output.strip():
            raise BuildDecisionAuditError(f"target {index} has invalid output")
        outcome = target.get("outcome")
        if outcome not in build_decisions.OUTCOMES:
            raise BuildDecisionAuditError(
                f"target {output!r} has unsupported outcome: {outcome!r}"
            )
        sources = target.get("sources")
        if not isinstance(sources, list) or any(
            not isinstance(value, str) or not value.strip() for value in sources
        ):
            raise BuildDecisionAuditError(
                f"target {output!r} sources must be a list of non-empty strings"
            )
    return targets


def _evaluate_target(
    target: dict[str, Any],
    changed_paths: set[str],
) -> dict[str, Any]:
    sources = [normalize_path(value) for value in target["sources"]]
    matched = sorted(changed_paths.intersection(sources))
    impact = "PROVEN" if matched else "NO_PROVEN_IMPACT"
    outcome = str(target["outcome"])

    if outcome == "ERROR":
        audit_result = "FAIL"
        reason = "TARGET_ERROR"
    elif impact == "PROVEN":
        if outcome == "BUILT":
            audit_result = "PASS"
            reason = "PROVEN_BUILT"
        elif outcome == "CACHE_RESTORED":
            audit_result = "PASS"
            reason = "PROVEN_CACHE_RESTORED"
        else:  # CURRENT; other values were rejected by validation.
            audit_result = "FAIL"
            reason = "PROVEN_LEFT_CURRENT"
    elif outcome == "BUILT":
        audit_result = "WARNING"
        reason = "POSSIBLE_OVERBUILD"
    elif outcome == "CACHE_RESTORED":
        audit_result = "PASS"
        reason = "NO_PROVEN_IMPACT_CACHE_RESTORED"
    else:  # CURRENT
        audit_result = "PASS"
        reason = "NO_PROVEN_IMPACT_CURRENT"

    return {
        "output": str(target["output"]),
        "outcome": outcome,
        "impact": impact,
        "matched_changed_sources": matched,
        "audit_result": audit_result,
        "reason": reason,
    }


def audit_report(
    decision_report: dict[str, Any],
    changed_paths: Iterable[str],
) -> dict[str, Any]:
    """Audit one structured build-decision report against explicit changed paths."""

    targets = _validated_targets(decision_report)
    normalized_changes = normalize_changed_paths(changed_paths)
    changed_set = set(normalized_changes)
    audited_targets = [_evaluate_target(target, changed_set) for target in targets]
    counts = Counter(target["audit_result"] for target in audited_targets)

    source_provenance = decision_report.get("provenance")
    source_commit_sha = (
        source_provenance.get("source_commit_sha")
        if isinstance(source_provenance, dict)
        else None
    )
    result = "FAIL" if counts.get("FAIL", 0) else "PASS"

    return {
        "schema": AUDIT_SCHEMA,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "source_report": {
            "schema": decision_report.get("schema"),
            "schema_version": decision_report.get("schema_version"),
            "kind": decision_report.get("kind"),
            "engine": decision_report.get("engine"),
            "backend_signature": decision_report.get("backend_signature"),
            "source_commit_sha": source_commit_sha,
        },
        "changed_paths": normalized_changes,
        "changed_path_count": len(normalized_changes),
        "target_count": len(audited_targets),
        "audit_counts": {
            value: counts.get(value, 0) for value in AUDIT_RESULTS
        },
        "result": result,
        "targets": audited_targets,
    }


def write_audit_report(
    *,
    decision_report: dict[str, Any],
    changed_paths: Iterable[str],
    output_path: Path,
) -> dict[str, Any]:
    """Audit and write the stable machine-readable result."""

    report = audit_report(decision_report, changed_paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def print_audit_summary(report: dict[str, Any]) -> None:
    """Print a concise human summary while JSON remains the API."""

    counts = report["audit_counts"]
    print(
        f"Build audit: targets={report['target_count']} "
        f"pass={counts['PASS']} warning={counts['WARNING']} fail={counts['FAIL']}"
    )
    for target in report["targets"]:
        print(
            f"  {target['audit_result'].lower()}: {target['output']} "
            f"[{target['reason']}]"
        )
