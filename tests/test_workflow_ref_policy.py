"""Semantic reusable-workflow reference policy.

Checks:
Released SCAD consumers keep reusable workflow callers on the same semantic
`tool.scad-project` release declared in project configuration. An opaque commit SHA in
consumer workflow YAML is rejected when the configured tool ref is a semantic release.
Development refs remain supported when explicitly configured.

Testing approach:
Temporary workflow files are validated with the real tooling policy. No Git checkout is
needed: these cases isolate the caller-ref contract and disable the optional workflow
environment marker so only project configuration versus YAML is compared.
"""

from pathlib import Path

from scad_project import __version__
from scad_project.config import ProjectContext
from scad_project.tooling import tooling_errors


def _context(root: Path, ref: str) -> ProjectContext:
    return ProjectContext(
        root=root,
        config_file=root / "project.scad.yml",
        config={
            "tooling": {
                "tool_scad_project": {
                    "path": "tools/tool.scad-project",
                    "ref": ref,
                }
            }
        },
    )


def _workflow(root: Path, ref: str) -> None:
    path = root / ".github" / "workflows" / "scad.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "jobs:\n"
        "  scad:\n"
        "    uses: brainboxemb/tool.scad-project/.github/workflows/"
        f"reusable-ci.yml@{ref}\n",
        encoding="utf-8",
    )


def test_semantic_project_ref_accepts_matching_workflow_tag(tmp_path, monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    expected = f"v{__version__}"
    _workflow(tmp_path, expected)

    assert tooling_errors(_context(tmp_path, expected)) == []


def test_semantic_project_ref_rejects_opaque_workflow_sha(tmp_path, monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    expected = f"v{__version__}"
    _workflow(tmp_path, "a" * 40)

    errors = tooling_errors(_context(tmp_path, expected))

    assert errors == [
        "reusable workflow ref mismatch: .github/workflows/scad.yml uses "
        + ("a" * 40)
        + f", project.yml expects {expected}"
    ]


def test_explicit_development_ref_must_match_workflow_ref(tmp_path, monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    _workflow(tmp_path, "feature/test-release")

    assert tooling_errors(_context(tmp_path, "feature/test-release")) == []
