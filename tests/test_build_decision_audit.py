"""Post-build decision audit policy and structured report contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scad_project import build_decision_audit
from scad_project import build_decisions


def _report(*targets: dict) -> dict:
    return {
        "schema": build_decisions.REPORT_SCHEMA,
        "schema_version": build_decisions.REPORT_SCHEMA_VERSION,
        "kind": "build",
        "engine": "scons",
        "backend_signature": "backend-test",
        "provenance": {"source_commit_sha": "source-sha"},
        "targets": list(targets),
    }


def _target(outcome: str, *sources: str, output: str = "bld/part.stl") -> dict:
    return {
        "output": output,
        "outcome": outcome,
        "sources": list(sources),
    }


@pytest.mark.parametrize(
    ("outcome", "expected_result", "expected_reason"),
    [
        ("BUILT", "PASS", "PROVEN_BUILT"),
        ("CACHE_RESTORED", "PASS", "PROVEN_CACHE_RESTORED"),
        ("CURRENT", "FAIL", "PROVEN_LEFT_CURRENT"),
        ("ERROR", "FAIL", "TARGET_ERROR"),
    ],
)
def test_proven_impact_policy(outcome, expected_result, expected_reason):
    report = build_decision_audit.audit_report(
        _report(_target(outcome, "dsg/main.scad", "dsg/shared.scad")),
        ["dsg/shared.scad"],
    )

    target = report["targets"][0]
    assert target["impact"] == "PROVEN"
    assert target["matched_changed_sources"] == ["dsg/shared.scad"]
    assert target["audit_result"] == expected_result
    assert target["reason"] == expected_reason
    assert report["result"] == ("FAIL" if expected_result == "FAIL" else "PASS")


@pytest.mark.parametrize(
    ("outcome", "expected_result", "expected_reason"),
    [
        ("CURRENT", "PASS", "NO_PROVEN_IMPACT_CURRENT"),
        ("CACHE_RESTORED", "PASS", "NO_PROVEN_IMPACT_CACHE_RESTORED"),
        ("BUILT", "WARNING", "POSSIBLE_OVERBUILD"),
        ("ERROR", "FAIL", "TARGET_ERROR"),
    ],
)
def test_no_proven_impact_policy(outcome, expected_result, expected_reason):
    report = build_decision_audit.audit_report(
        _report(_target(outcome, "dsg/main.scad")),
        ["README.md"],
    )

    target = report["targets"][0]
    assert target["impact"] == "NO_PROVEN_IMPACT"
    assert target["matched_changed_sources"] == []
    assert target["audit_result"] == expected_result
    assert target["reason"] == expected_reason


def test_transitive_source_and_multiple_changes_prove_impact():
    report = build_decision_audit.audit_report(
        _report(
            _target(
                "BUILT",
                "dsg/render/main.scad",
                "dsg/components/shared.scad",
                "dsg/components/leaf.scad",
            )
        ),
        ["README.md", "dsg/components/leaf.scad"],
    )

    assert report["targets"][0]["impact"] == "PROVEN"
    assert report["targets"][0]["matched_changed_sources"] == [
        "dsg/components/leaf.scad"
    ]


def test_changed_paths_are_normalized_and_deduplicated():
    report = build_decision_audit.audit_report(
        _report(_target("BUILT", "dsg/components/shared.scad")),
        [
            r"dsg\components\shared.scad",
            "./dsg/components/shared.scad",
            "dsg/components/../components/shared.scad",
        ],
    )

    assert report["changed_paths"] == ["dsg/components/shared.scad"]
    assert report["changed_path_count"] == 1
    assert report["targets"][0]["impact"] == "PROVEN"


def test_report_counts_warnings_without_failing_overall():
    report = build_decision_audit.audit_report(
        _report(
            _target("CURRENT", "dsg/a.scad", output="bld/a.stl"),
            _target("BUILT", "dsg/b.scad", output="bld/b.stl"),
        ),
        ["README.md"],
    )

    assert report["result"] == "PASS"
    assert report["audit_counts"] == {"PASS": 1, "WARNING": 1, "FAIL": 0}


def test_write_audit_report_preserves_structured_source_identity(tmp_path: Path):
    output = tmp_path / "audit.json"
    report = build_decision_audit.write_audit_report(
        decision_report=_report(_target("BUILT", "dsg/a.scad")),
        changed_paths=["dsg/a.scad"],
        output_path=output,
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["schema"] == build_decision_audit.AUDIT_SCHEMA
    assert report["schema_version"] == 1
    assert report["source_report"] == {
        "schema": build_decisions.REPORT_SCHEMA,
        "schema_version": 1,
        "kind": "build",
        "engine": "scons",
        "backend_signature": "backend-test",
        "source_commit_sha": "source-sha",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda report: report.update(schema="unknown"),
        lambda report: report.update(schema_version=99),
        lambda report: report.update(targets={}),
        lambda report: report["targets"][0].update(outcome="UNKNOWN"),
        lambda report: report["targets"][0].pop("sources"),
    ],
)
def test_invalid_or_unknown_decision_evidence_fails_closed(mutation):
    report = _report(_target("BUILT", "dsg/a.scad"))
    mutation(report)

    with pytest.raises(build_decision_audit.BuildDecisionAuditError):
        build_decision_audit.audit_report(report, ["dsg/a.scad"])
