"""Reusable aggregate SCAD production workflow contract.

Checks:
The shared production workflow performs a host-side Moon affected decision before the
single heavy SCAD container, uses minimal exact-revision checkouts, retains independent
normal/verification SCons caches, invokes one repository aggregate task, stages generic
Build/Verification trees, and delegates publication to lightweight generic tooling.

Testing approach:
The workflow YAML is inspected as contract text. End-to-end event, cache and container
behavior is qualified separately against the reference template before release.
"""

from pathlib import Path


WORKFLOW = Path(".github/workflows/project-production.yml")
GIT_TOOL_RELEASE = "ce7c81c39ebc70933b4150028aa74d928a53c2ba"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_preflight_uses_minimal_blobless_exact_revision_checkout():
    text = _text()

    assert "fetch-depth: 0" not in text
    assert text.count("fetch-depth: 1") >= 2
    assert text.count("filter: blob:none") >= 2
    assert text.count("submodules: false") >= 2
    assert 'git fetch --no-tags --depth=1 origin "$BASE_SHA"' in text
    assert "github.event.pull_request.base.sha" in text
    assert "github.event.before" in text


def test_released_moon_preflight_gates_the_only_scad_container():
    text = _text()

    affected_use = f"brainboxemb/tool.git-project/moon/affected@{GIT_TOOL_RELEASE}"
    moon_use = f"brainboxemb/tool.git-project/moon@{GIT_TOOL_RELEASE}"
    assert affected_use in text
    assert moon_use in text
    assert text.index(affected_use) < text.index("container:")
    assert text.count("container:") == 1
    assert "if: needs.preflight.outputs.affected == 'true'" in text
    assert "image: ghcr.io/brainboxemb/scad-toolchain:v0.4.1" in text


def test_uncertain_or_forced_ranges_run_conservatively():
    text = _text()

    missing_revision = "0000000000000000000000000000000000000000"
    assert missing_revision in text
    assert "Force requested; preflight will deliberately fail conservative." in text
    assert "No unambiguous event base is available" in text
    assert "generic Moon preflight will run conservatively" in text


def test_production_bootstraps_dependencies_only_after_the_gate():
    text = _text()

    bootstrap = "bash ./bootstrap.sh"
    assert bootstrap in text
    assert text.index("container:") < text.index(bootstrap)
    assert "tools/tool.git-project/git-project.sh validate --repo ." in text
    assert "scad-project.sh tooling-check" in text


def test_build_and_verify_keep_separate_scons_caches():
    text = _text()

    assert "path: .cache/scad-project/scons" in text
    assert "path: .cache/scad-project/verification-scons" in text
    assert "scad-production-build-scons-v1-" in text
    assert "scad-production-verification-scons-v1-" in text
    assert text.count("Run or hydrate aggregate SCAD production graph") == 1


def test_generic_materialization_validation_does_not_encode_template_outputs():
    text = _text()

    assert "build_path:" in text
    assert "verification_path:" in text
    assert "AGGREGATE_TASK" in text
    assert '"source_revision": os.environ["SOURCE_SHA"]' in text
    assert '"status": "success"' in text
    assert '"exit_code": 0' in text
    for template_specific in (
        "tube-holder-assembly",
        "tube-holder-bore-check",
        "mounting-plate-thickness-check",
    ):
        assert template_specific not in text


def test_publication_runs_outside_scad_container_through_generic_workflow():
    text = _text()

    publisher = (
        "brainboxemb/tool.git-project/.github/workflows/"
        f"reusable-generated-output-publish.yml@{GIT_TOOL_RELEASE}"
    )
    assert text.count(publisher) == 2
    assert "Publish Build output" in text
    assert "Publish Verification output" in text
    assert "source_revision: ${{ needs.preflight.outputs.source_sha }}" in text
