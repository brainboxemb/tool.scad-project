from pathlib import Path


ROOT = Path(".github/workflows")
RELEASE = ROOT / "project-release.yml"
BUILD = ROOT / "project-build.yml"
VERIFY = ROOT / "project-verify.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_workflow_preflights_before_build_and_verify():
    text = read(RELEASE)

    assert "jobs:\n  preflight:" in text
    assert "\n  build:" in text
    assert "\n  verify:" in text
    assert "\n  finalize:" in text
    assert text.count("needs: preflight") == 2
    assert "needs: [preflight, build, verify]" in text

    assert text.count("publish: false") == 2
    assert text.count("source_ref: ${{ inputs.source_sha }}") == 2
    assert text.count("release_version: ${{ inputs.version }}") == 2
    assert text.count("source_sha: ${{ inputs.source_sha }}") >= 2


def test_release_preflight_requires_source_on_production_branch():
    text = read(RELEASE)

    assert 'PRODUCTION_BRANCH="$(python - <<\'PY\'' in text
    assert 'production.get("source_branch", "main")' in text
    assert "git merge-base --is-ancestor" in text
    assert "is not on production branch" in text


def test_release_workflow_finalizes_branches_before_tag_and_github_release():
    text = read(RELEASE)

    publish = text.index("name: Publish immutable release branches")
    tag = text.index("name: Create annotated release tag")
    github_release = text.index("name: Create GitHub Release and upload assets")

    assert publish < tag < github_release
    assert "scad-project release-publish-branches" in text
    assert "scad-project release-package" in text
    assert "scad-project release-notes" in text
    assert ".release/SHA256SUMS.txt" in text


def test_release_workflow_checks_exact_source_and_existing_release_namespace():
    text = read(RELEASE)

    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in text
    assert '"${ACTUAL_SHA}" != "${RELEASE_SOURCE_SHA}"' in text
    assert 'refs/tags/${RELEASE_VERSION}' in text
    assert 'gh release view "${RELEASE_VERSION}"' in text
    assert 'git ls-remote --heads origin "refs/heads/${BUILD_BRANCH}"' in text
    assert 'git ls-remote --heads origin "refs/heads/${VERIFICATION_BRANCH}"' in text


def test_release_workflow_rolls_back_tag_and_browseable_branches_on_failure():
    text = read(RELEASE)

    assert "Roll back incomplete release finalization" in text
    assert "failure() && steps.publish-branches.outcome == 'success'" in text
    assert 'git push origin ":refs/tags/${RELEASE_VERSION}"' in text
    assert 'git push origin --delete "${BUILD_BRANCH}"' in text
    assert 'git push origin --delete "${VERIFICATION_BRANCH}"' in text


def test_build_and_verify_support_exact_release_source_context():
    for workflow in (BUILD, VERIFY):
        text = read(workflow)
        assert "source_ref:" in text
        assert "release_version:" in text
        assert "source_sha:" in text
        assert "SCAD_PROJECT_RELEASE_VERSION: ${{ inputs.release_version }}" in text
        assert "SCAD_PROJECT_SOURCE_SHA: ${{ inputs.source_sha || github.sha }}" in text
        assert "ref: ${{ inputs.source_ref || github.ref }}" in text


def test_release_workflow_uses_feature_self_refs_only_during_pr_development():
    text = read(RELEASE)

    assert (
        "brainboxemb/tool.scad-project/.github/workflows/project-build.yml@"
        "feature/versioned-project-release"
    ) in text
    assert (
        "brainboxemb/tool.scad-project/.github/workflows/project-verify.yml@"
        "feature/versioned-project-release"
    ) in text
