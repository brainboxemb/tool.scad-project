"""Repository-level Migration-005 SCAD production workflow policy.

Checks:
The reusable workflow keeps one hosted job and one Docker runtime, performs one
released Moon impact query before runtime acquisition, makes the exact base SCAD
tool gitlink available for shallow base/head comparison, consumes the SCAD-owned
execution plan, restores only configured SCons caches, retains compact evidence
instead of full normal output artifacts, preserves the resolved exact source SHA
for host-side publication provenance, finishes current-run information on the
host, stages durable orchestration/run-context evidence through the SCAD owner
helper, and overlaps isolated Build/Verification publishers without another runner.

Testing approach:
Parse the workflow job boundary and inspect the reusable workflow source for the
pinned cross-repository contracts and explicit structural/resource invariants.
The base-gitlink helper itself has an integration-style shallow Git regression
test in test_fetch_base_gitlink_commit.py; orchestration content is qualified in
test_orchestration_observability.py.
"""

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/project-production.yml")
CLEANUP_WORKFLOW = Path(".github/workflows/project-pr-cleanup.yml")


def test_production_workflow_uses_one_host_orchestrator_job():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    assert list(data["jobs"]) == ["production"]
    job = data["jobs"]["production"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert "container" not in job


def test_production_workflow_uses_compact_publication_namespace_defaults():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    inputs = data[True]["workflow_call"]["inputs"]

    assert inputs["build_branch_suffix"]["default"] == "bld"
    assert inputs["verification_branch_suffix"]["default"] == "vrf"

    cleanup = CLEANUP_WORKFLOW.read_text(encoding="utf-8")
    assert "for SUFFIX in bld vrf; do" in cleanup
    assert "for KIND in build verification; do" not in cleanup


def test_production_workflow_uses_one_moon_impact_query_and_v028_contract():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("brainboxemb/tool.git-project/moon/affected@v0.2.8") == 1
    assert "brainboxemb/tool.git-project/moon/affected@v0.2.7" not in text
    assert "affected-tasks" in text
    assert "scad_project.ci_policy" in text
    assert "consumer:scad.docs" in text


def test_production_workflow_fetches_only_the_exact_base_scad_tool_gitlink():
    text = WORKFLOW.read_text(encoding="utf-8")

    base_fetch = text.index("Fetch only the exact comparison base")
    current_tool = text.index("Initialize pinned shared SCAD task policy")
    base_tool = text.index("Make exact base SCAD task policy revision available")
    impact = text.index("Query affected Moon tasks once")
    assert base_fetch < current_tool < base_tool < impact
    assert "scripts/fetch_base_gitlink_commit.sh" in text
    assert '"$BASE_SHA"' in text
    assert "tools/tool.scad-project" in text
    assert "fetch-depth: 0" not in text


def test_production_workflow_exports_exact_source_for_host_publication_provenance():
    text = WORKFLOW.read_text(encoding="utf-8")

    source_validation = text.index("source_sha must resolve to an exact 40-character commit SHA")
    source_export = text.index('echo "SCAD_PROJECT_SOURCE_SHA=$source_sha" >> "$GITHUB_ENV"')
    checkout = text.index("Checkout exact source for host orchestration")
    build_publication = text.index("scad-project publication-info-build")
    verification_publication = text.index("scad-project publication-info-verification")

    assert source_validation < source_export < checkout
    assert source_export < build_publication < verification_publication
    assert text.count('SCAD_PROJECT_SOURCE_SHA=$source_sha') == 1


def test_production_workflow_starts_at_most_one_capability_appropriate_runtime():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("docker run --rm") == 1
    assert "steps.plan.outputs.runtime_image" in text
    assert "ghcr.io/brainboxemb/scad-toolchain:v0.4.1" not in text
    assert "SCAD_TOOLCHAIN_VERSION: v0.5.1" in text
    assert "PYTHONDONTWRITEBYTECODE" in text
    assert "MATERIALIZATION_CAPABILITIES" in text


def test_production_workflow_transports_only_configured_scons_caches():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "steps.plan.outputs.use_scons_cache == 'true'" in text
    assert "steps.plan.outputs.use_verification_scons_cache == 'true'" in text
    assert "scad-production-build-scons-v2" in text
    assert "scad-production-verification-scons-v2" in text


def test_normal_production_retains_only_compact_orchestration_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("actions/upload-artifact@") == 1
    assert "Upload compact SCAD orchestration evidence" in text
    assert "scad-build-publication\n          if-no-files-found" not in text
    assert "scad-verification-publication\n          if-no-files-found" not in text


def test_current_run_finishing_and_staging_happen_after_moon_on_host():
    text = WORKFLOW.read_text(encoding="utf-8")

    runtime = text.index("Execute or hydrate required SCAD capabilities in one Docker process")
    build_index = text.index("scad-project build-index")
    publication_info = text.index("scad-project publication-info-build")
    staging = text.index("scripts/stage_publication.py")
    publisher = text.index("Publish changed Build and Verification families concurrently on this runner")
    assert runtime < build_index < publication_info < staging < publisher
    assert text.count("scripts/stage_publication.py") == 2
    assert '--source-sha "$SOURCE_SHA"' in text
    assert '--base-sha "$BASE_SHA"' in text
    assert "add_orchestration()" not in text
    assert "GITHUB_RUN_ID" not in text.split("docker run --rm", 1)[1].split("'\n", 1)[0]


def test_build_and_verification_publication_can_overlap_on_same_runner():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "generated-output-publish.sh" in text
    assert "Publish changed Build and Verification families concurrently on this runner" in text
    assert ") >\"$RUNNER_TEMP/${name}-publisher.log\" 2>&1 &" in text
    assert "wait \"${pids[$i]}\"" in text
    assert "generated-output/publish@" not in text
    assert "reusable-generated-output-publish.yml" not in text
    assert "persist-credentials: false" in text
    assert "-e GITHUB_TOKEN" not in text


def test_production_workflow_planner_install_uses_declared_build_requirements():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python -m pip install --disable-pip-version-check -e ./tools/tool.scad-project" in text
    assert "--no-build-isolation" not in text
