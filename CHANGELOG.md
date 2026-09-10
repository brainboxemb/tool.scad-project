# Changelog

Functional changes to released `tool.scad-project` versions.

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

- Explicit `builds:` entries remain supported as compatibility/exception overrides instead of being required for every normal render/export entrypoint.

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
