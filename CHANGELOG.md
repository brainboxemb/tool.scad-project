# Changelog

Functional changes to released `tool.scad-project` versions.

## v0.14.10

### Fixed

- Correct released owner guidance to use canonical `dev/pr-N/{bld,vrf}`, `prod/{bld,vrf}` and `rel/vX.Y.Z/{bld,vrf}` technical publication namespaces, matching the already-qualified v0.14.9 runtime/default behavior.
- Add regression coverage preventing released `AGENTS.md` from drifting back to legacy `build` / `verification` publication branch examples.

## v0.14.9

### Changed

- Normalize current-generation persistent generated-output technical namespaces to `bld` and `vrf` for pull-request, production and coordinated-release publication, matching the existing SCAD workspace roots.
- Keep Build and Verification as readable lifecycle/semantic names while retaining explicit custom branch overrides and historical already-published `build`/`verification` branches as historical evidence.
- Align PR cleanup, examples, documentation, release browse links and regression coverage with `dev/pr-N/{bld,vrf}`, `prod/{bld,vrf}` and `rel/vX.Y.Z/{bld,vrf}`.

## v0.14.8

### Fixed

- Publish `tool.scad-project` semantic release tags as lightweight refs that point directly at the already-qualified release commit, allowing nested reusable workflows to resolve through cross-repository `@vX.Y.Z` calls.
- Add regression coverage for the lightweight release-tag contract exposed by final Migration-005 template release qualification.

## v0.14.7

### Fixed

- Preserve the resolved exact production source SHA through host-side Build/Verification finishing so `publication-info.txt` records the actual assessed and produced source revision instead of GitHub's synthetic pull-request merge SHA.
- Add production-workflow regression coverage that requires exact source provenance to be exported before checkout and host publication finishing.

## v0.14.6

### Added

- Persist coarse current-run production phase timings from preflight/planning through snapshot preparation and expose them as `orchestration/timings.json` plus a readable generated-output timing table.
- Retain post-snapshot generated-branch publication timing in compact CI orchestration evidence and extend that compact evidence retention to 90 days.

### Changed

- Keep detailed Moon/SCons/OpenSCAD logs and per-capability materialization timings as the lower-level evidence while making workflow-level timing directly navigable from generated Build and Verification output.

## v0.14.5

### Fixed

- Run shared `scad.docs`, `scad.build` and `scad.verify` Moon capability wrappers with the immutable SCAD runtime's guaranteed `python3` executable instead of assuming an unavailable `python` alias.
- Add regression coverage for the shared capability launcher contract so future Moon policy changes cannot silently reintroduce the unsupported alias.

## v0.14.4

### Added

- Add durable orchestration evidence that keeps producer execution timing, current Moon materialization timing and snapshot-preparation timing distinct, while exposing the retained raw Moon/producer logs directly from generated-output navigation.
- Add shallow-upgrade regression coverage and an exact base-gitlink fetch helper so affected-task evaluation can compare a consumer whose `tool.scad-project` gitlink changed between base and head.

### Changed

- Move release-request branch parsing, validation and cleanup into the shared release workflow so consumer release workflows can remain thin trigger/permission/reusable-workflow callers.
- Align consumer reusable SCAD workflow calls to the configured semantic `tool.scad-project` release ref while retaining the parent gitlink as the exact resolved source identity.
- Make `workflow-sync` and tooling validation preserve and enforce that semantic released workflow ref instead of rewriting consumers to an opaque commit SHA.

### Fixed

- Prevent shallow base-to-head affected queries from falling back conservatively with `bad object` when the base revision references an older `tool.scad-project` gitlink commit that is not present in the shallow submodule checkout.
- Restore durable, human-navigable access to the complete current orchestration logs and step durations after earlier evidence compaction made those details difficult to find once GitHub Actions logs expired.

## v0.14.3

### Fixed

- Make shared Moon capability outputs describe stable materialized capability output instead of requiring optional SCons state and domain-report files that are absent for direct-engine consumers or verification commands without SCons targets.
- Add regression coverage for the shared Moon output contract so direct and SCons consumers can use the same capability definitions without false `missing_outputs` failures.

## v0.14.2

### Fixed

- Read inherited Moon capability selection from project-level root `moon.yml` via `workspace.inheritedTasks.include`, matching Moon 2.5.4 instead of placing that project-level selection in `.moon/workspace.yml`.
- Align the Migration-005 consumer configuration guidance and release markers with the corrected root `moon.yml` capability-selection model.

## v0.14.1

### Fixed

- Let normal production planner installation use the PEP 517 build requirements declared in `pyproject.toml` instead of assuming `setuptools` and `wheel` are already installed in a fresh hosted Python environment.
- Add a clean-environment planner-install smoke test so the reusable production workflow is qualified without hidden build-backend state.

## v0.14.0

### Added

- Add shared inherited Moon capability policy for `scad.docs`, `scad.build` and `scad.verify`, so consumers select real SCAD capabilities without copying lifecycle task implementations.
- Add SCAD-owned CI planning that validates the visible Moon capability set against `project.scad.yml`, selects the OpenSCAD-focused or full/dual v0.5.0 runtime, and derives applicable normal/Verification SCons cache transport.
- Expose affected versus publication-safe materialization scope explicitly so a complete generated Build tree can hydrate unchanged contributors without falsely classifying them as source-affected.

### Changed

- Consume the complete affected-task list from released `tool.git-project v0.2.8` once per normal run and start no SCAD planner/image/runtime for an unrelated change.
- Execute or hydrate required coarse capabilities in one explicit Docker process on one hosted runner, using `docker.scad-toolchain v0.5.0` and `PYTHONDONTWRITEBYTECODE=1`.
- Keep normal SCons transport only for SCons-configured Build/docs work and keep the separate Verification-SCons cache only when real verification render/export targets exist.
- Move Build index/publication information and current impact/materialization evidence out of Moon source-derived task identity and into host finishing after execution/hydration.
- Stop uploading duplicate complete Build and Verification Actions artifacts during normal production; retain compact orchestration evidence and publish local staging trees directly.
- Allow independent Build/Verification publishers to overlap on the same host without adding another runner.
- Derive coordinated-release runtime and cache policy from the same SCAD planner while preserving complete Build/Verification artifacts as the required cross-job release hand-off.
- Align reusable Build, Verify, Production and PR-cleanup workflow markers plus the package runtime version at v0.14.0.

### Fixed

- Avoid broad `tools/tool.scad-project/**` Moon inputs that could admit generated Python bytecode and destabilize source-derived task hashes across fresh runners.
- Preserve unchanged presentation or documentation contributors when only one Build-family capability is affected, preventing complete generated-output branch publication from dropping unaffected content.

## v0.13.1

### Changed

- Collapse normal repository production into one host orchestrator job while retaining Moon host preflight and exactly one explicit immutable SCAD Docker process for affected work.
- Reuse the same shallow exact-source worktree and pinned Moon runtime across preflight, container execution and host validation instead of crossing a second production checkout/job boundary.
- Publish prepared Build and Verification trees sequentially from the host job through released `tool.git-project` v0.2.7 same-job generated-output tooling, keeping write credentials outside the SCAD container.
- Keep README-only or otherwise unaffected changes at zero SCAD image pulls/container starts and preserve conservative forced production when source/base context is uncertain.

### Fixed

- Use explicit SCons cache restore/save actions so cold affected runs save reusable normal and verification cache snapshots with valid keys.
- Do not attempt generated-output publication for unsupported manual feature-branch contexts.

## v0.13.0

### Added

- Add `project-production.yml` as the reusable repository-level SCAD production workflow with host-side Moon affected preflight, one conditional heavy SCAD container and lightweight generated-output publication.
- Add an optional `affected_task` so consumers can keep the source-impact gate separate from an environment-sensitive publication-ready `aggregate_task` while still using one authoritative Moon graph.
- Retain host preflight decision evidence and validate current Moon materialization before prepared Build and Verification output is published.

### Changed

- Use shallow blobless exact-source checkouts and fetch only the exact comparison base required for Moon instead of requiring full repository history.
- Reuse the explicit BASE/HEAD range in the production container through `MOON_BASE` and `MOON_HEAD`; missing or unusable comparison context forces conservative execution instead of risking a false skip.
- Keep normal Build and Verification as logically independent consumer tasks with separate SCons caches even when the publication-ready aggregate is executed in one heavy job.
- Keep dependency bootstrap and the SCAD container behind the affected gate; unrelated changes can finish after host preflight without initializing SCAD dependencies or the runtime image.
- Keep generated-output publication outside the SCAD container through released `tool.git-project` lifecycle tooling.

## v0.12.0

### Added

- Add `scad-project build-audit` as an explicit post-build check for schema-v1 SCons build-decision reports and caller-supplied changed paths.
- Add `scad-project.build-decision-audit` schema version 1 with per-target proven-impact classification, stable reason codes and pass/warning/fail results.
- Accept changed paths directly with repeatable `--changed-path` options or from newline-delimited `--changed-paths-file` inputs, with optional explicit audit output location.
- Preserve machine-readable audit evidence before returning a failing exit status when a proven affected target is incorrectly reported `CURRENT` or build evidence already contains `ERROR`.

### Changed

- Reuse the existing per-target `sources` dependency evidence for audit decisions instead of introducing a second dependency model.
- Treat rebuilds without proven changed-source impact as warnings rather than correctness failures in the first audit contract.
- Keep generic Git/GitHub changed-path discovery and automatic workflow enforcement outside this release; the audit receives explicit changed paths and remains independently invokable.

## v0.11.0

### Added

- Add persistent `brainboxemb.execution-evidence` schema-v1 envelopes and one canonical human-readable log for the existing `scad.docs`, `scad.build` and `scad.verify` producer capabilities.
- Retain relevant structured SCons decision reports with producer output under `evidence/domain/`, so persistent domain evidence is created by the SCAD producer instead of synthesized later by consumer CI.
- Add generated Build/Verification navigation that distinguishes artifacts, producer execution evidence, SCAD domain evidence, orchestration/materialization evidence and publication context.

### Changed

- Keep producer evidence attached to the existing `design-build`, `build` and `verify` actions while preserving separate Moon task boundaries; do not replace the visible SCAD graph with one coarse producer wrapper.
- Keep Moon/current materialization evidence and publication finalization outside the SCAD producer evidence contract. Cached or hydrated producer evidence therefore remains tied to the execution that created it while current materialization records the revision/context that consumed it.
- Keep local non-Git SCAD actions usable by skipping persistent execution evidence with a warning when exact source/owner revisions cannot be resolved; persistent CI/publication consumers are expected to require and validate the evidence files.

## v0.10.1

### Added

- Add `scad-project produce-build` as the stable complete normal-build producer action for repository-level orchestrators. It owns SCAD validation, generated design documentation, configured build output, build indexing and producer provenance while preserving SCons as the fine-grained target/cache authority.
- Add `scad-project produce-verification` as the corresponding complete verification producer action. It owns verification-relevant validation, verification-only targets/project checks and producer provenance without invoking normal Build, generated design output or the normal build index.
- Resolve producer source/tool revisions from the actual Git checkout when available while preserving explicit CI provenance overrides, so cached producer evidence remains tied to the execution that created it.

### Changed

- Keep Moon/GitHub cache restore, current materialization evidence and generated-branch publication outside the SCAD producer actions; those remain repository-orchestration/lifecycle concerns rather than SCAD target semantics.

## v0.10.0

### Changed

- Make `scad-project verify` the single verification-domain action: it validates verification-relevant project state, builds declared verification-only targets, and then runs configured verification commands without invoking the normal `build` domain.
- Keep normal Build output and `.cache/scad-project/scons` outside the reusable Verify workflow; Verify now restores/writes only `.cache/scad-project/verification-scons` and reports only `last-verification-build.json`.
- Treat the Build/Verify separation as an intentional breaking release boundary so consumers adopt the new contract only when they explicitly upgrade to v0.10.0.

### Removed

- Remove the separate public `scad-project functional-verify` command; its verification-target and command behavior is now part of `scad-project verify`.

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
- Allow the cleanup workflow to delete the merged same-repository pull request source branch so feature branches do not accumulate after merge.

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
- Generate deterministic build, verification and STL release ZIPs plus `SHA256SUMS.txt` and verify those checksums before immutable publication and upload.
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