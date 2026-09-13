"""Stable SCAD producer action contract.

Checks:
The normal producer composes validation, generated design documentation, normal
configured output, build indexing and producer provenance in that order. The
verification producer composes validation, verification-only targets/project checks
and producer provenance without invoking normal Build. The public CLI exposes both
producer actions as direct domain commands.

Testing approach:
Unit tests monkeypatch the existing domain functions at the producer boundary so the
contract can be checked without running OpenSCAD/SCons. CLI tests replace context
loading/config validation and assert direct dispatch to the producer functions.
"""

from __future__ import annotations

import sys

import pytest

from scad_project import cli, producer


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


def test_build_producer_composes_complete_build_result(monkeypatch):
    context = object()
    calls: list[str] = []

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

    assert calls == ["validate", "design", "build", "index", "provenance:build"]


def test_verification_producer_never_runs_normal_build(monkeypatch):
    context = object()
    calls: list[str] = []

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

    assert calls == ["validate", "verify", "provenance:verification"]


def test_producer_validation_failure_stops_before_generation(monkeypatch):
    context = object()
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
