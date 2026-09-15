"""Repository-level Migration-005 SCAD production workflow policy.

Checks:
The reusable workflow keeps one hosted job and one Docker runtime, performs one
released Moon impact query before runtime acquisition, consumes the SCAD-owned
execution plan, restores only configured SCons caches, retains compact evidence
instead of full normal output artifacts, finishes current-run information on the
host, and overlaps isolated Build/Verification publishers without another runner.

Testing approach:
Parse the workflow job boundary and inspect the reusable workflow source for the
pinned cross-repository contracts and explicit structural/resource invariants.
"""

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/project-production.yml")


def test_production_workflow_uses_one_host_orchestrator_job():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    assert list(data["jobs"]) == ["production"]
    job = data["jobs"]["production"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert "container" not in job


def test_production_workflow_uses_one_moon_impact_query_and_v028_contract():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("brainboxemb/tool.git-project/moon/affected@v0.2.8") == 1
    assert "brainboxemb/tool.git-project/moon/affected@v0.2.7" not in text
    assert "affected-tasks" in text
    assert "scad_project.ci_policy" in text
    assert "consumer:scad.docs" in text


def test_production_workflow_starts_at_most_one_capability_appropriate_runtime():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("docker run --rm") == 1
    assert "steps.plan.outputs.runtime_image" in text
    assert "ghcr.io/brainboxemb/scad-toolchain:v0.4.1" not in text
    assert "SCAD_TOOLCHAIN_VERSION: v0.5.0" in text
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


def test_current_run_finishing_happens_after_moon_on_host():
    text = WORKFLOW.read_text(encoding="utf-8")

    runtime = text.index("Execute or hydrate required SCAD capabilities in one Docker process")
    build_index = text.index("scad-project build-index")
    publication_info = text.index("scad-project publication-info-build")
    assert runtime < build_index < publication_info
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
