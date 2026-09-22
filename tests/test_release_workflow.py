"""Release workflow safety and consumer boundary.

Checks:
The reusable release workflow owns release-request parsing and cleanup, validates the
exact current production commit before building and again before publication, derives
runtime/cache policy from the same SCAD project plan used by normal production, runs
Build and Verify before finalization, verifies checksums before publishing, publishes
immutable branches before creating the tag/GitHub Release, and contains rollback steps
for incomplete finalization. Consumer workflows therefore only need triggers,
permissions and one reusable-workflow call.

Testing approach:
GitHub Actions workflows cannot be meaningfully executed as a local unit test, so these
tests inspect the workflow YAML source itself. They check release request ownership,
resolved value hand-off, required jobs/dependencies, plan hand-off, commands and
ordering. End-to-end behavior is additionally exercised in a reference consumer; this
module protects the shared boundary and safety rules from accidental YAML edits.
"""

from pathlib import Path


ROOT = Path(".github/workflows")
RELEASE = ROOT / "project-release.yml"
BUILD = ROOT / "project-build.yml"
VERIFY = ROOT / "project-verify.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_workflow_owns_request_resolution_and_cleanup():
    text = read(RELEASE)

    assert "jobs:\n  resolve:" in text
    assert "name: Resolve release request" in text
    assert 'REF_NAME: ${{ github.ref_name }}' in text
    assert 'ACTOR: ${{ github.actor }}' in text
    assert 'REPOSITORY_OWNER: ${{ github.repository_owner }}' in text
    assert 'release-request/*' in text
    assert 'release request branch must be release-request/vX.Y.Z/<40-char-sha>' in text
    assert 'version=${version}' not in text
    assert 'echo "version=$version" >> "$GITHUB_OUTPUT"' in text
    assert 'echo "source_sha=$source_sha" >> "$GITHUB_OUTPUT"' in text

    assert "\n  cleanup-request:" in text
    assert "always() && github.event_name == 'push'" in text
    assert "startsWith(github.ref_name, 'release-request/')" in text
    assert 'git push origin --delete "$REQUEST_BRANCH" || true' in text


def test_release_workflow_accepts_optional_caller_inputs_and_exposes_resolved_outputs():
    text = read(RELEASE)

    assert "description: Optional immutable release version" in text
    assert "description: Optional exact 40-character source commit SHA" in text
    assert text.count("required: false") >= 4
    assert "value: ${{ jobs.resolve.outputs.version }}" in text
    assert "value: ${{ jobs.resolve.outputs.source_sha }}" in text


def test_release_workflow_preflights_before_build_and_verify():
    text = read(RELEASE)

    assert "\n  preflight:" in text
    assert "\n  build:" in text
    assert "\n  verify:" in text
    assert "\n  finalize:" in text
    assert "needs: resolve" in text
    assert text.count("needs: [resolve, preflight]") == 2
    assert "needs: [resolve, preflight, build, verify]" in text

    assert text.count("publish: false") == 2
    assert text.count("source_ref: ${{ needs.resolve.outputs.source_sha }}") == 2
    assert text.count("release_version: ${{ needs.resolve.outputs.version }}") == 2
    assert text.count("source_sha: ${{ needs.resolve.outputs.source_sha }}") >= 2


def test_release_preflight_uses_resolved_release_identity():
    text = read(RELEASE)

    assert "RELEASE_VERSION: ${{ needs.resolve.outputs.version }}" in text
    assert "RELEASE_SOURCE_SHA: ${{ needs.resolve.outputs.source_sha }}" in text
    assert "SCAD_PROJECT_RELEASE_VERSION: ${{ needs.resolve.outputs.version }}" in text
    assert "SCAD_PROJECT_SOURCE_SHA: ${{ needs.resolve.outputs.source_sha }}" in text
    assert "ref: ${{ needs.resolve.outputs.source_sha }}" in text
    assert "RELEASE_VERSION: ${{ inputs.version }}" not in text
    assert "RELEASE_SOURCE_SHA: ${{ inputs.source_sha }}" not in text


def test_release_preflight_derives_runtime_and_cache_policy_once():
    text = read(RELEASE)

    assert "name: Resolve SCAD release runtime and cache policy" in text
    assert "from scad_project.ci_policy import build_ci_plan" in text
    assert "plan = build_ci_plan(load_context(Path.cwd()))" in text
    assert "runtime_profile: ${{ steps.scad-plan.outputs.runtime_profile }}" in text
    assert "runtime_image: ${{ steps.scad-plan.outputs.runtime_image }}" in text
    assert "use_scons_cache: ${{ steps.scad-plan.outputs.use_scons_cache }}" in text
    assert (
        "use_verification_scons_cache: "
        "${{ steps.scad-plan.outputs.use_verification_scons_cache }}"
    ) in text

    assert "runtime_image: ${{ needs.preflight.outputs.runtime_image }}" in text
    assert (
        "use_scons_cache: ${{ needs.preflight.outputs.use_scons_cache == 'true' }}"
        in text
    )
    assert (
        "use_verification_scons_cache: "
        "${{ needs.preflight.outputs.use_verification_scons_cache == 'true' }}"
    ) in text


def test_release_preflight_requires_current_production_head():
    text = read(RELEASE)

    assert 'PRODUCTION_BRANCH="$(python - <<\'PY\'' in text
    assert 'production.get("source_branch", "main")' in text
    assert 'PRODUCTION_SHA="$(git rev-parse "refs/remotes/origin/${PRODUCTION_BRANCH}")"' in text
    assert '"$RELEASE_SOURCE_SHA" != "$PRODUCTION_SHA"' in text
    assert "must equal current $PRODUCTION_BRANCH HEAD" in text
    assert "git merge-base --is-ancestor" not in text
    assert 'echo "production_branch=$PRODUCTION_BRANCH" >> "$GITHUB_OUTPUT"' in text


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
    assert '"$ACTUAL_SHA" != "$RELEASE_SOURCE_SHA"' in text
    assert 'refs/tags/${RELEASE_VERSION}' in text
    assert 'gh release view "$RELEASE_VERSION"' in text
    assert 'git ls-remote --heads origin "refs/heads/${BUILD_BRANCH}"' in text
    assert 'git ls-remote --heads origin "refs/heads/${VERIFICATION_BRANCH}"' in text


def test_release_workflow_rolls_back_tag_and_browseable_branches_on_failure():
    text = read(RELEASE)

    assert "Roll back incomplete release finalization" in text
    assert "failure() && steps.publish-branches.outcome == 'success'" in text
    assert 'git push origin ":refs/tags/${RELEASE_VERSION}"' in text
    assert 'git push origin --delete "$BUILD_BRANCH"' in text
    assert 'git push origin --delete "$VERIFICATION_BRANCH"' in text


def test_build_and_verify_support_exact_release_source_context():
    for workflow in (BUILD, VERIFY):
        text = read(workflow)
        assert "source_ref:" in text
        assert "release_version:" in text
        assert "source_sha:" in text
        assert "runtime_image:" in text
        assert "SCAD_PROJECT_RELEASE_VERSION: ${{ inputs.release_version }}" in text
        assert "SCAD_PROJECT_SOURCE_SHA: ${{ inputs.source_sha || github.sha }}" in text
        assert "ref: ${{ inputs.source_ref || github.ref }}" in text
        assert "image: ${{ inputs.runtime_image }}" in text


def test_release_keeps_complete_artifacts_as_cross_job_handoff():
    release = read(RELEASE)
    build = read(BUILD)
    verify = read(VERIFY)

    assert "artifact_name: scad-project-release-build" in release
    assert "artifact_name: scad-project-release-verification" in release
    assert "name: Download verified build output" in release
    assert "name: Download verified verification output" in release
    assert "name: Upload generated build" in build
    assert "name: Upload verification evidence" in verify


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


def test_build_and_verify_materialize_declared_dependencies_before_domain_work():
    for workflow, domain_step in (
        (BUILD, "Describe build caches"),
        (VERIFY, "Describe verification cache"),
    ):
        text = read(workflow)
        bootstrap = text.index("name: Materialize declared project dependencies")
        domain = text.index(domain_step)

        assert bootstrap < domain
        assert (
            'bash ./tools/tool.git-project/git-project.sh bootstrap --repo "$GITHUB_WORKSPACE"'
            in text
        )
        assert "submodules: recursive" not in text
