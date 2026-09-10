# Changelog

Functional changes to released `tool.scad-project` versions.

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
- Multi-size profile expansion using `sizes`, passed to OpenSCAD as `-D size="..."`.
- Profile-level PNG `image_size` overrides with directory defaults and project-level fallback.

### Changed

- Explicit `builds:` entries remain supported for compatibility/exception overrides instead of being required for every normal render/export entrypoint.

## v0.6.1

### Added

- Unified `publication-info.txt` provenance for generated build and verification output.
- Immutable SCAD toolchain image/version recorded by reusable workflows.
- `tool.scad-project` release recorded with generated output.
- Runtime component inventory from `scad-toolchain-info`, including the actual
  OpenSCAD, PythonSCAD, BOSL2, pybosl2, Shapely, docsgen and Pillow versions.

### Changed

- `publication-info.txt` is the current-generation replacement for the classic
  `openscad-build.txt` metadata concept.

## v0.6.0

### Added

- SCAD toolchain v0.4.0 runtime baseline.
- Project-controlled PNG watermark orchestration through
  `rendering.watermark.text`.
- Public `scad-image-watermark` runtime integration.
- Permanent release workflow for immutable tool releases.
