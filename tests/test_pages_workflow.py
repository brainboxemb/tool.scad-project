"""GitHub Pages publication

Checks:
The generated unit-test overview can be published through GitHub Pages without writing
HTML back to the source branch. Publication follows a successful Test run on main or a
manual request, skips cleanly while Pages is disabled, and uses the current GitHub Pages
actions with the agreed short timeouts.

Testing approach:
These tests read the workflow as configuration rather than starting a deployment. They
check the trigger and guard expressions, the Pages actions and output paths, and the
special HTTP 404 handling that treats a not-yet-enabled Pages site as a normal skip.
"""

from pathlib import Path

import yaml


WORKFLOW_PATH = Path(".github/workflows/pages.yml")


def _workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _steps(job):
    return {step["name"]: step for step in job["steps"]}


def test_pages_workflow_has_safe_triggers_and_disabled_site_guard():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "workflow_run:" in text
    assert "- Test" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text

    # A repository with Pages disabled returns HTTP 404 from the Pages API. That state
    # must skip publication rather than make an otherwise healthy main branch red.
    assert '404)' in text
    assert 'enabled=false' in text
    assert "Source: GitHub Actions" in text
    assert "Unexpected GitHub Pages API response" in text


def test_pages_workflow_builds_only_the_small_public_site():
    workflow = _workflow()
    build = workflow["jobs"]["build"]
    steps = _steps(build)

    assert build["if"] == "needs.pages-state.outputs.enabled == 'true'"
    assert steps["Checkout documentation source"]["uses"] == "actions/checkout@v6"
    assert steps["Configure GitHub Pages"]["uses"] == "actions/configure-pages@v5"
    assert (
        steps["Upload GitHub Pages artifact"]["uses"]
        == "actions/upload-pages-artifact@v4"
    )
    assert steps["Upload GitHub Pages artifact"]["with"]["path"] == "bld/pages"

    build_command = steps["Build Pages content"]["run"]
    assert "scripts/generate_test_reference.py" in build_command
    assert "bld/pages/tests/index.html" in build_command
    assert "bld/pages/index.html" in build_command
    assert 'href="./tests/"' in build_command


def test_pages_workflow_deploys_with_expected_environment_and_actions():
    workflow = _workflow()
    deploy = workflow["jobs"]["deploy"]
    steps = _steps(deploy)

    assert deploy["if"] == "needs.pages-state.outputs.enabled == 'true'"
    assert deploy["environment"]["name"] == "github-pages"
    assert deploy["environment"]["url"] == "${{ steps.deployment.outputs.page_url }}"
    assert steps["Deploy GitHub Pages"]["uses"] == "actions/deploy-pages@v4"


def test_pages_workflow_timeouts_stay_short():
    workflow = _workflow()

    for job_name in ("pages-state", "build", "deploy"):
        job = workflow["jobs"][job_name]
        assert job["timeout-minutes"] == 5
        for step in job["steps"]:
            assert step["timeout-minutes"] == 2
