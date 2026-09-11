# Changelog

Functional changes to released `tool.scad-project` versions.

## v0.9.13

### Added

- Add dependency-aware verification-only OpenSCAD render/export targets through `verification.render_root` and `verification.export_root`, with their own `verification.output_root` and optional `verification.image_size`.
- Add verification profile `output_pattern` support so size-expanded verification targets can keep stable project-specific filenames.
- Add a separate persistent `verification-scons` cache and `last-verification-build.json` report so unchanged verification evidence can be restored target-by-target.

### Changed

- Keep the normal build SCons cache restore-only in Verify while verification-only targets use a separate restore/write cache.
- Build declared verification targets before project-specific `verification.commands`, allowing cheap README/index generation after reused or rebuilt geometry without forcing unrelated OpenSCAD renders.

## v0.9.12

### Changed

- Define the canonical PR-first agent workflow centrally in `AGENTS.md`: reserve the final pull-request number with a temporary issue, create `feature/pr-<number>-<slug>`, convert that exact issue into the same-number draft PR, and keep subsequent work attached to that PR.
- Clarify that the actual PR number is authoritative for `dev/pr-<number>/build` and `dev/pr-<number>/verification`; never guess a future PR number or reuse an unrelated issue number.
- Align the central publication guidance with the v0.9.11 PR-scoped model and make consumer root `AGENTS.md` files defer to the pinned tool policy for branch/PR/publication workflow.
- Clarify the central watermark policy so configured build/design PNGs and project verification commands use the shared `scad-image-watermark` runtime command instead of duplicating image-processing logic.

## v0.9.11

### Added

- Publish pull-request build and verification previews to isolated `dev/pr-<number>/build` and `dev/pr-<number>/verification` branches instead of one shared development destination.
- Add `publication.development.pr_branch_prefix` for configuring the pull-request preview namespace while keeping `dev/pr` as the default.
- Add `scad-project publication-cleanup-pr --pr-number N` and a reusable PR-cleanup workflow that removes generated preview branches when a pull request closes.
- Allow the cleanup workflow to delete the merged same-repository source branch so feature branches do not accumulate after merge.

### Changed

- Treat ordinary non-production branch pushes as artifact-only by default; development publication now belongs to the pull request where the PR number provides a collision-free namespace.
- Keep legacy shared development-branch publication available only as an explicit `publication.development.publish_branch_pushes: true` migration opt-in.
- Let reusable Build and Verify workflows publish same-repository pull-request previews while preserving artifact-only behaviour for fork pull requests.

## v0.9.10

### Fixed

- Make Build and Verify cache-input hashing independent of the consumer repository layout instead of assuming CAD/design sources live under `dsg/`.
- Track repository-wide OpenSCAD, Python, render/export profile, design metadata and common imported-asset inputs so layouts such as `lib.scad.hub75` invalidate stale generated-design snapshots correctly.
- Add regression coverage that rejects a return to hard-coded `dsg/**` cache patterns.

## v0.9.9

### Fixed

- Apply the configured `rendering.watermark.text` post-processing to generated design PNGs, matching normal render outputs.
- Apply design-image watermarking through both the direct design builder and the dependency-selective SCons design backend.
- Keep the unwatermarked intermediate PNG private to the build step so cached/published design output contains only the final watermarked image.

## v0.9.8

### Fixed

- Pin consumer Build, Verify and Release reusable workflow callers to the exact checked-out `tool.scad-project` commit SHA instead of the semantic version tag, avoiding GitHub validation failures when nested reusable workflows are reached through an annotated tag.
- Keep `project.yml` free to express the semantic tool dependency (`vX.Y.Z`) while the workflow callers use the corresponding immutable commit SHA.
- Keep root and `bootstrap/` updater scripts synchronized and add regression coverage for the distinction between semantic dependency refs and exact workflow pins.

## v0.9.7

### Fixed

- Use explicit GitHub self-repository (`$/`) references when the reusable project release workflow nests Build and Verify, so cross-repository release consumers resolve the complete workflow chain at one tool revision.
- Add regression coverage for the nested release references and validate the cross-repository release preflight path without creating release side effects.

## v0.9.6

### Fixed

- Update consumer `project-release.yml` reusable workflow refs together with `project-build.yml` and `project-verify.yml` when `update-repo.ps1` or `update-repo.sh` advances `tool.scad-project`.
- Keep root updater scripts and their canonical `bootstrap/` copies covered by regression tests so release workflow support cannot silently drift again.

### Changed

- Derive the default tooling-test release ref from the package runtime version instead of duplicating the current version as a hard-coded test constant.

## v0.9.5

### Fixed

- Run the selective rebuild summary with `python3`, matching the immutable SCAD toolchain runtime, instead of assuming a `python` alias exists.
- Add regression coverage so the Build workflow cannot silently return to the unavailable `python` command.

## v0.9.4

### Changed

- Rename workflow cache steps and key prefixes around their purpose: selective build reuse versus an exact generated-design snapshot.
- Split Build cache restore/save into explicit steps so cache matches and writes are visible instead of appearing only as automatic post-job cache actions.
- Add a GitHub job summary that explains exact hits, fallback hits and cold-cache misses in ordinary language.
- Report selective rebuild counts for design images and configured outputs so the practical value of the cache is visible without reading the full SCons log.
- Align the Verify cache input hash with Build while keeping Verify restore-only, so an already-populated Build cache can be reported as an exact hit for the same source state.

### Fixed

- Preserve the v0.9.3 Build-writes / Verify-restores cache policy with explicit restore/save actions and regression coverage for the readable cache workflow.

## v0.9.3

### Fixed

- Make the reusable Verify workflow restore the shared SCons cache read-only, leaving Build as the only cache writer.
- Prevent a parallel Verify run from publishing a newer cache snapshot that contains configured-build objects but omits generated-design objects, which could force unchanged design images to render again on the next Build restore-key fallback.
- Add regression coverage for the Build-writes / Verify-restores cache policy.

## v0.9.2

### Added

- Add dependency-selective generated design rendering for SCons consumers with one SCons target per generated design PNG.
- Track OpenSCAD design renders through their source document, generated entrypoint and scanned transitive OpenSCAD dependencies.
- Track PythonSCAD design renders conservatively against project and configured-external Python sources until Python import scanning is available.
- Emit `last-design-build.json` with executed versus restored/current design targets.

### Changed

- Keep the existing whole-tree `bld/design` cache as the exact-hit fast path, but let a cache miss fall through to per-image SCons reuse instead of re-rendering every design image.
- Include generated-design inputs in the persistent SCons cache key so design-only changes can populate reusable per-image cache objects.

## v0.9.1

### Added

- Generate `bld/png/README.md` automatically as a browseable Markdown gallery whenever the generated build contains a PNG directory.
- Include generated PNGs in deterministic path order, including nested PNG paths.
- Link the root generated build index directly to the PNG gallery README.

## v0.9.0

### Added

- Add a reusable, coordinated project release workflow with fail-fast preflight, exact-source Build and Verify jobs, and finalization only after both succeed.
- Publish mutable production snapshots to `prod/build` and `prod/verification` by default, while retaining configurable production/development branch names.
- Publish immutable browseable release snapshots to `rel/<version>/build` and `rel/<version>/verification` without force-pushing existing release branches.
- Generate deterministic build, verification and STL release ZIPs plus `SHA256SUMS.txt`, and verify those checksums before immutable publication and upload.
- Generate GitHub Release notes from the project's configured changelog and link to the browseable immutable build and verification branches.
- Record coordinated release context, exact source SHA, tag, tool/submodule pins and runtime provenance in generated release snapshots.
- Add rollback for incomplete release finalization and a self-cleaning consumer `release-request/vX.Y.Z/<sha>` trigger pattern.

### Changed

- Require a project release source SHA to equal the current configured production-branch HEAD at preflight time, and revalidate that HEAD immediately before immutable finalization.
- Make generated build indexes publication-aware so they report the resolved `prod/*` or `rel/<version>/*` destination instead of a hard-coded legacy branch name.
- Use same-revision local reusable Build/Verify calls from the release workflow so nested release jobs cannot drift to a different `tool.scad-project` revision.

### Fixed

- Document and enforce the `actions: read` caller permission required by reusable release workflows that download Build and Verify artifacts.
- Avoid GitHub workflow-ref permission failures caused by attempting to release an older production-branch ancestor after workflow files have advanced.

## v0.8.0

### Added

- Add the optional `build_engine.engine: scons` backend behind the existing `scad-project build` interface while keeping `direct` as the backwards-compatible default.
- Discover OpenSCAD dependencies transitively through `use` and `include`, and track literal `import()` / `surface()` file inputs as leaf dependencies.
- Fail safely for dynamic OpenSCAD file-loading expressions that cannot be represented deterministically in the SCons dependency graph.
- Persist SCons `CacheDir` data across clean GitHub-hosted runners so unchanged outputs can be restored without carrying `bld/` or `.sconsign` between runs.
- Emit a compact SCons build report with executed versus restored/current targets.
- Cache the complete generated `bld/design` tree in the reusable Build workflow and skip `design-build` on an exact design-input cache hit.

### Changed

- Move reusable Build, Verify and tool tests to immutable `docker.scad-toolchain` v0.4.1 with SCons 4.11.1 included in the runtime image.
- Namespace build caches by repository, toolchain version, exact checked-out `tool.scad-project` gitlink and relevant build inputs.
- Include render/export profile files and common imported CAD/data/image assets in cache input hashing.

## v0.7.3

### Added

- Add `design.include_externals` project policy, defaulting to `true` for backwards compatibility.
- Allow consumer projects to omit configured-external design documentation while keeping external CAD source dependencies available.
- Mark omitted external design documentation explicitly in the generated design index instead of reporting it as missing.

## v0.7.2

### Changed

- Bound reusable Build and Verify jobs to 15 minutes.
- Bound setup, lint, artifact and publication steps to 2 minutes.
- Bound design rendering, configured output builds and verification work to 5 minutes.
- Bound the tool test workflow to 15 minutes and the release workflow to 10 minutes.
- Add regression coverage for the workflow timeout policy.

## v0.7.1

### Fixed

- Align the package runtime version and reusable workflow version markers with the released tool version.
- Add regression coverage so package and workflow version markers cannot silently drift apart again.

## v0.7.0

### Added

- Directory-based OpenSCAD build discovery through configured `render_root` and `export_root` paths.
- Optional `render.yml` and `export.yml` build profiles beside entrypoints.
- Multi-size profile expansion using `sizes`, passed to OpenSCAD as `-D size=\"...\"`.
- Profile-level PNG `image_size` overrides with directory defaults and project-level fallback.

### Changed

- Explicit `builds:` entries remain supported for compatibility/exception overrides instead of being required for every normal render/export entrypoint.

## v0.6.1

### Added

- Unified `publication-info.txt` provenance for generated build and verification output.
- Immutable SCAD toolchain image/version recorded by reusable workflows.
- `tool.scad-project` release recorded with generated output.
- Runtime component inventory from `scad-toolchain-info`, including the actual OpenSCAD, PythonSCAD, BOSL2, pybosl2, Shapely, docsgen and Pillow versions.

### Changed

- `publication-info.txt` is the current-generation replacement for the classic `openscad-build.txt` metadata concept.

## v0.6.0

### Added

- SCAD toolchain v0.4.0 runtime baseline.
- Project-controlled PNG watermark orchestration through `rendering.watermark.text`.
- Public `scad-image-watermark` runtime integration.
- Permanent release workflow for immutable tool releases.
