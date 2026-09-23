# Deterministic SCons decision conformance

This document records the white-box SCons decision contract exercised by
`tool.scad-project` itself. It complements the structured decision-report contract in
[`build-decision-telemetry.md`](build-decision-telemetry.md).

The conformance suite belongs in this repository because the SCons driver, dependency
scanner, target-signature model and cache ownership are SCAD-tool implementation
behavior. Independent black-box qualification and GitHub Actions cache-adapter tests
remain later roadmap layers.

## Test shape

The suite runs the real `scons_driver.py` against SCons itself. A tiny synthetic
OpenSCAD graph and a temporary fake `openscad` executable keep execution fast while
still exercising:

- transitive `include` and `use` discovery;
- static `import()` and `surface()` leaf dependencies;
- explicit SCons source dependencies;
- the production-style `Value(target-spec)` signature input;
- backend/tool signature invalidation;
- `.sconsign` state;
- real SCons `CacheDir` restore behavior;
- the Step-1 structured outcome reporter.

Assertions use the machine-readable outcomes `BUILT`, `CACHE_RESTORED`, `CURRENT`
and `ERROR`; console wording is not treated as an API.

## Conformance scenarios

The deterministic matrix covers at least:

| Scenario | Required decision behavior |
| --- | --- |
| cold workspace, empty CacheDir | all requested targets `BUILT` |
| identical second run | existing unchanged targets `CURRENT` |
| private dependency change | only dependent target rebuilds |
| shared dependency change | all dependent targets rebuild |
| static `import()` / `surface()` asset change | only dependent target rebuilds |
| target-spec/profile change | only target with changed target spec rebuilds |
| backend/tool signature change | affected targets rebuild according to the shared signature |
| local output deleted while state/cache remain | missing target is repaired from CacheDir when available |
| fresh workspace/state with populated CacheDir | matching targets `CACHE_RESTORED`, builder not executed |
| partial CacheDir | available target restored, missing target built |
| add target | only new/otherwise affected work occurs |
| remove target | removed target is no longer active |
| build and verification cache scopes | one scope does not restore from the other scope |

The production-wiring tests additionally assert that normal builds use
`build_engine.SCONS_CACHE_ROOT` and verification uses
`verification.VERIFICATION_SCONS_CACHE_ROOT`, and that those roots remain distinct.

## Fresh-runner simulation

Cache restore tests deliberately model a CI-style fresh runner:

1. build the fixture and populate a real SCons `CacheDir`;
2. preserve/copy the cache snapshot;
3. remove outputs and `.sconsign`/state;
4. restore only the cache snapshot;
5. execute SCons again;
6. assert structured target outcomes and whether the builder ran.

This isolates SCons cache semantics from GitHub Actions cache transport. Actions-level
exact-hit/fallback/miss behavior is a separate roadmap layer.

## Cache content-integrity boundary

`CACHE_RESTORED` means that SCons located a cache entry for the target build signature
and restored it without executing the builder. It does **not** mean that
`tool.scad-project` independently proved the restored bytes are the expected artifact.

With the pinned SCons 4.11.1 behavior, a readable cache file selected by the build
signature is copied to the target; SCons does not compare the payload against a
separate expected artifact-content checksum during restore. The conformance suite
therefore includes a characterization test in which a readable cache payload is
externally modified and is still restored as `CACHE_RESTORED` without builder
execution.

That test is intentional. It prevents later code from confusing build-decision
telemetry with artifact-integrity validation. Whether the ecosystem needs an
additional integrity layer is a separate policy/risk decision to reassess before
broad consumer rollout.

## Non-goals

This suite does not:

- implement the Step-3 post-build decision auditor;
- validate GitHub Actions cache key/fallback transport;
- create the future independent `tool.scad-project.test` qualification repository;
- duplicate dependency-scanner tests for dynamic/unresolvable file expressions;
- add an artifact checksum/integrity layer.

Those concerns remain separate so this suite stays a deterministic contract for the
SCons decision engine itself.
