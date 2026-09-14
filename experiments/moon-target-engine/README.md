# Experiment — Moon as SCAD target engine

Status: **parked / not active**

## Question

Can Moon replace all or part of the current SCons target-execution layer in `tool.scad-project` without losing the fine-grained OpenSCAD dependency and cache behaviour that is already qualified?

## Why this is separate from Migration 004

Migration 004 is about the repository execution model: Build/Verify aggregation, container startup, affected/preflight decisions, publication placement and understandable project-versus-library behaviour.

Replacing the SCAD target engine at the same time would make that migration too broad and would make performance/correctness results hard to attribute.

For Migration 004, SCons remains the qualified fine-grained target engine.

## Current behaviour that a replacement must preserve

The current implementation uses `openscad_deps.py` independently of SCons to discover:

- recursive `use` / `include` dependencies;
- static `import` / `surface` dependencies;
- configured search paths;
- unsafe/dynamic references that cannot be included safely in a cache signature.

SCons then registers those dependencies per configured PNG/STL target, giving target-level selective invalidation and cache restoration.

A Moon-based replacement must not regress this to one coarse `**/*.scad` invalidation boundary unless that loss is explicitly measured and accepted.

## Candidate experiment

Compare at least:

1. current Moon-at-repository-level + SCons-at-target-level;
2. one coarse Moon task per Build/Verify domain;
3. fine-grained Moon tasks generated from `tool.scad-project` target configuration and the existing OpenSCAD dependency scanner.

## Required scenarios

- cold build;
- unchanged rerun;
- one target entrypoint changed;
- one transitive include used by only one target changed;
- one shared include changed;
- imported asset changed;
- unrelated README/documentation change;
- verification-only target change;
- cache/hydration restoration;
- decision/evidence readability.

## Decision rule

Do not replace SCons unless the Moon-based model is at least as correct and selective while materially simplifying the stack or improving execution/caching/evidence.

This experiment is intentionally parked until Migration 004 has settled the higher-level repository execution model.
