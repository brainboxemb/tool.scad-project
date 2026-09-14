# SCAD producer execution evidence

`tool.scad-project` retains a small domain-neutral execution envelope alongside its
richer SCAD/SCons decision telemetry. The common JSON contract is owned by
`tool.git-project`; this repository owns the SCAD capability boundaries and the
content of the SCAD producer log.

## Capability boundary

Persistent producer evidence is attached to the existing domain actions:

| CLI action | Capability | Execution id | Persistent output |
| --- | --- | --- | --- |
| `design-build` | `scad.docs` | `scad-docs` | normal build root |
| `build` | `scad.build` | `scad-build` | normal build root |
| `verify` | `scad.verify` | `scad-verify` | verification output root |

`build-index`, publication/provenance actions and repository-level graph aggregation
are not producer executions merely because an orchestrator exposes them as tasks.
Moon should keep these actions visible as separate tasks rather than hiding them
behind one coarse SCAD wrapper.

## Persistent layout

Each producer execution owns one canonical pair:

```text
evidence/
  executions/
    <execution-id>/
      execution.json
      execution.log
  domain/
    <SCAD/SCons report>.json
```

`execution.json` uses `brainboxemb.execution-evidence` schema version 1. It records
at least the capability, action owner, exact producer source revision, exact
`tool.scad-project` owner revision, status, exit code, canonical log and links to
richer domain evidence.

`execution.log` is intentionally concise. It summarizes the producer identity and,
when structured SCons telemetry exists, the `BUILT`, `CACHE_RESTORED`, `CURRENT`
and `ERROR` decisions. It is not a second copy of raw OpenSCAD/SCons stdout.
Detailed target sources, signatures, cache decisions and other SCAD-specific facts
remain in the structured domain report.

## Producer versus materialization evidence

Producer evidence belongs to the output that was actually produced and is therefore
part of the cacheable/hydratable producer result. A later equivalent source revision
may hydrate that output without rewriting its producer `source_revision`.

Current orchestration evidence remains separate and is added by the consumer's
repository-level orchestration/publication workflow:

```text
orchestration/
  materialization.json
  moon.log
```

`materialization.json` describes the current source revision/context for which Moon
executed or hydrated the graph. `moon.log` explains the current execution/cache
choice. After hydration it is valid and expected for the materialization revision to
differ from the retained producer revision.

Publication/finalization likewise consumes prepared output. It may add
`publication-info.txt` and generated-branch context, but must not synthesize or
rewrite producer execution evidence.

## Generated README navigation

Normal Build indexing and Verification output expose an evidence map that distinguishes:

- artifacts;
- producer execution evidence;
- SCAD domain evidence;
- orchestration/materialization evidence;
- publication context.

Navigation points at canonical files; evidence is not duplicated merely to make it
easier to find.

## Local and production behavior

A normal local SCAD action can still run outside a Git checkout. If exact producer or
owner revisions cannot be resolved, persistent execution evidence is skipped with a
warning rather than making the CAD action itself Git-only.

Persistent CI/publication consumers are stricter: their acceptance checks must require
the expected `execution.json`/`execution.log` files and validate the common schema.
This makes exact revision evidence mandatory for published snapshots while preserving
local/tool unit-test compatibility.
