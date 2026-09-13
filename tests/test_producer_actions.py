"""Stable SCAD producer action contract.

Checks:
The normal producer composes producer revision context, validation, generated design
documentation, normal configured output, build indexing and producer provenance in
that order. The verification producer composes revision context, validation,
verification-only targets/project checks and producer provenance without invoking
normal Build. Producer revision context comes from the real checkout while explicit
CI overrides remain authoritative. The public CLI exposes both producer actions.

Testing approach:
Unit tests monkeypatch the existing domain functions at the producer boundary so the
contract can be checked without running OpenSCAD/SCons. A small fake project context
checks producer revision environment setup. CLI tests replace context loading/config
validation and assert direct dispatch to the producer functions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scad_project import cli, producer


class _FakeContext:
    root = Path("/repo")
    config = {
        "tooling": {
            "tool_scad_project": {
                "path": "tools/tool.scad-project",
            }
        }
    }

    def path(self, value: str) -> Path:
        return self.root / value


def test_shared_producer_validation_aggregates_existing_domain_checks(monkeypatch):
    context = object()
    monkeypatch.setattr(producer, "tooling_errors", lambda ctx: ["tooling"])
    monkeypatch.setattr(producer, "validate_externals_config", lambda ctx: ["external-config"])
    monkeypatch.setattr(producer, "check_externals", lambda ctx: ["external-state"])
    monkeypatch.setattr(producer, "lint_docs", lambda ctx: ["docs"])
    monkeypatch.setattr(producer, "lint_design", lambda ctx: ([], ["design"]))

    assert producer._producer_validation_errors(context) == [
        "tooling",
        "external-config",
        "external-state",
        "docs",
        "design",
    ]


def test_producer_provenance_uses_exact_checkouts_without_overriding_ci(monkeypatch):
    context = _FakeContext()
    source_sha = "1" * 40
    tool_sha = "2" * 40

    def fake_head(path: Path) -> str | None:
        if path == context.root:
            return source_sha
        if path == context.root / "tools/tool.scad-project":
            return tool_sha
        return None

    monkeypatch.setattr(producer, "_git_head", fake_head)
    for name in (
        "SCAD_PROJECT_SOURCE_SHA",
        "SCAD_PROJECT_TOOL_SHA",
        "SCAD_PROJECT_WORKFLOW_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    producer._ensure_producer_provenance(context)

    assert producer.os.environ["SCAD_PROJECT_SOURCE_SHA"] == source_sha
    assert producer.os.environ["SCAD_PROJECT_TOOL_SHA"] == tool_sha
    assert producer.os.environ["SCAD_PROJECT_WORKFLOW_VERSION"] == f"v{producer.__version__}"

    monkeypatch.setenv("SCAD_PROJECT_SOURCE_SHA", "explicit-source")
    monkeypatch.setenv("SCAD_PROJECT_TOOL_SHA", "explicit-tool")
    monkeypatch.setenv("SCAD_PROJECT_WORKFLOW_VERSION", "explicit-version")
    producer._ensure_producer_provenance(context)

    assert producer.os.environ["SCAD_PROJECT_SOURCE_SHA"] == "explicit-source"
    assert producer.os.environ["SCAD_PROJECT_TOOL_SHA"] == "explicit-tool"
    assert producer.os.environ["SCAD_PROJECT_WORKFLOW_VERSION"] == "explicit-version"


def test_build_producer_composes_complete_build_result(monkeypatch):
    context = object()
    calls: list[str] = []

    monkeypatch.setattr(producer, "_ensure_producer_provenance", lambda ctx: calls.append("revision"))
    monkeypatch.setattr(producer, "_require_valid_producer_context", lambda ctx: calls.append("validate"))
    monkeypatch.setattr(producer, "build_design", lambda ctx: calls.append("design"))
    monkeypatch.setattr(producer, "build_project", lambda ctx: calls.append("build"))
    monkeypatch.setattr(producer, "write_build_index", lambda ctx: calls.append("index"))
    monkeypatch.setattr(
        producer,
        "write_publication_info",
        lambda ctx, kind: calls.append(f"provenance:{kind}"),
    )

    producer.produce_build(context)

    assert calls == [
        "revision",
        "validate",
        "design",
        "build",
        "index",
        "provenance:build",
    ]


def test_verification_producer_never_runs_normal_build(monkeypatch):
    context = object()
    calls: list[str] = []

    monkeypatch.setattr(producer, "_ensure_producer_provenance", lambda ctx: calls.append("revision"))
    monkeypatch.setattr(producer, "_require_valid_producer_context", lambda ctx: calls.append("validate"))
    monkeypatch.setattr(
        producer,
        "build_project",
        lambda ctx: pytest.fail("verification producer must not run normal Build"),
    )
    monkeypatch.setattr(
        producer,
        "build_design",
        lambda ctx: pytest.fail("verification producer must not generate normal design output"),
    )
    monkeypatch.setattr(
        producer,
        "write_build_index",
        lambda ctx: pytest.fail("verification producer must not write the normal build index"),
    )
    monkeypatch.setattr(
        producer,
        "run_functional_verification",
        lambda ctx: calls.append("verify"),
    )
    monkeypatch.setattr(
        producer,
        "write_publication_info",
        lambda ctx, kind: calls.append(f"provenance:{kind}"),
    )

    producer.produce_verification(context)

    assert calls == ["revision", "validate", "verify", "provenance:verification"]


def test_producer_validation_failure_stops_before_generation(monkeypatch):
    context = object()
    monkeypatch.setattr(producer, "_ensure_producer_provenance", lambda ctx: None)
    monkeypatch.setattr(producer, "_producer_validation_errors", lambda ctx: ["invalid"])
    monkeypatch.setattr(
        producer,
        "build_design",
        lambda ctx: pytest.fail("generation must not start after failed validation"),
    )

    with pytest.raises(RuntimeError, match="invalid"):
        producer.produce_build(context)


def _prepare_cli(monkeypatch):
    context = object()
    monkeypatch.setattr(cli, "load_context", lambda project: context)
    monkeypatch.setattr(cli, "validate_config", lambda ctx: [])
    monkeypatch.setattr(cli, "validate_build_engine_config", lambda ctx: [])
    monkeypatch.setattr(cli, "validate_release_config", lambda ctx: [])
    return context


def test_cli_dispatches_build_producer(monkeypatch, capsys):
    context = _prepare_cli(monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(cli, "produce_build", lambda ctx: calls.append(ctx))
    monkeypatch.setattr(sys, "argv", ["scad-project", "produce-build"])

    cli.main()

    assert calls == [context]
    assert "build producer: OK" in capsys.readouterr().out


def test_cli_dispatches_verification_producer(monkeypatch, capsys):
    context = _prepare_cli(monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(cli, "produce_verification", lambda ctx: calls.append(ctx))
    monkeypatch.setattr(sys, "argv", ["scad-project", "produce-verification"])

    cli.main()

    assert calls == [context]
    assert "verification producer: OK" in capsys.readouterr().out
