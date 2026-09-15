"""Repository-level SCAD production workflow policy.

Checks:
The reusable production workflow has one host orchestrator job, keeps the
expensive SCAD runtime behind the Moon affected decision, uses the immutable
SCAD image through one explicit Docker process, keeps source checkout write
credentials out of that process, and publishes with the exact released generic
same-job publisher rather than a second reusable-workflow job.

Testing approach:
Parse the workflow for its structural job boundary and inspect the source text
for the pinned generic orchestration/publication interfaces and credential /
container policy that must remain visible and reviewable.
"""

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
    assert (
        f"brainboxemb/tool.git-project/generated-output/publish@{GIT_TOOL_RELEASE_SHA}"
        in text
    )
    assert "reusable-generated-output-publish.yml" not in text
    assert "persist-credentials: false" in text
    assert "-e GITHUB_TOKEN" not in text
