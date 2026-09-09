# Changelog

Functional changes to released `tool.scad-project` versions.

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
