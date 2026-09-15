"""Contract tests for the repository-level SCAD production workflow."""

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/project-production.yml")
GIT_TOOL_RELEASE_SHA = "6234b7437b0dc0115642468f74d1f4a2c2214bef"


def test_production_workflow_uses_one_host_orchestrator_job():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    assert list(data["jobs"]) == ["production"]
    job = data["jobs"]["production"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert "container" not in job


def test_production_workflow_keeps_container_conditional_and_publication_host_side():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "brainboxemb/tool.git-project/moon/affected@v0.2.7" in text
    assert "docker run" in text
    assert "ghcr.io/brainboxemb/scad-toolchain:v0.4.1" in text
    assert f"brainboxemb/tool.git-project/generated-output/publish@{GIT_TOOL_RELEASE_SHA}" in text
    assert "reusable-generated-output-publish.yml" not in text
