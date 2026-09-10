"""Release workflow safety

Checks:
The reusable release workflow must validate the exact current production commit before
building and again before publication, run Build and Verify before finalization, verify
checksums before publishing, publish immutable branches before creating the tag/GitHub
Release, and contain rollback steps for incomplete finalization. Nested reusable
workflows must use the explicit self-repository references required for cross-repository
consumers.

Testing approach:
GitHub Actions workflows cannot be meaningfully executed as a local unit test, so these
tests inspect the workflow YAML source itself. They check for the required jobs,
dependencies, commands and ordering. End-to-end behavior is additionally exercised in
the template reference consumer; this module protects the safety rules from accidental
YAML edits.
"""

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


def test_release_preflight_requires_current_production_head():
    text = read(RELEASE)

    assert 'PRODUCTION_BRANCH="$(python - <<\'PY\'' in text
    assert 'production.get("source_branch", "main")' in text
    assert 'PRODUCTION_SHA="$(git rev-parse "refs/remotes/origin/${PRODUCTION_BRANCH}")"' in text
    assert '"${RELEASE_SOURCE_SHA}" != "${PRODUCTION_SHA}"' in text
    assert "must equal current ${PRODUCTION_BRANCH} HEAD" in text
    assert "git merge-base --is-ancestor" not in text
    assert 'echo "production_branch=${PRODUCTION_BRANCH}" >> "$GITHUB_OUTPUT"' in text


def test_release_finalizer_revalidates_production_head_before_side_effects():
    text = read(RELEASE)

    revalidate = text.index("name: Revalidate production source and release namespace")
    package = text.index("name: Package release downloads")
    publish = text.index("name: Publish immutable release branches")

    assert revalidate < package < publish
    assert "PRODUCTION_BRANCH: ${{ needs.preflight.outputs.production_branch }}" in text
    assert "advanced after preflight" in text
    assert text.count('PRODUCTION_SHA="$(git rev-parse "refs/remotes/origin/${PRODUCTION_BRANCH}")"') == 2


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


def test_release_workflow_verifies_generated_checksums_before_publication():
    text = read(RELEASE)

    package = text.index("name: Package release downloads")
    checksums = text.index("name: Verify release checksums")
    publish = text.index("name: Publish immutable release branches")

    assert package < checksums < publish
    assert "sha256sum -c SHA256SUMS.txt" in text


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


def test_release_workflow_uses_self_repository_reusable_workflows():
    """Guard the cross-repository release fix that requires explicit self references."""
    text = read(RELEASE)

    assert "uses: $/.github/workflows/project-build.yml" in text
    assert "uses: $/.github/workflows/project-verify.yml" in text
    assert "uses: ./.github/workflows/project-build.yml" not in text
    assert "uses: ./.github/workflows/project-verify.yml" not in text
    assert "brainboxemb/tool.scad-project/.github/workflows/project-build.yml@" not in text
    assert "brainboxemb/tool.scad-project/.github/workflows/project-verify.yml@" not in text
    assert "@feature/versioned-project-release" not in text
