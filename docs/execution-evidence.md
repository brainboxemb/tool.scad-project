# SCAD producer execution evidence

`tool.scad-project` retains a small domain-neutral execution envelope alongside its
richer SCAD/SCons decision telemetry. The common JSON contract is owned by
`tool.git-project`; this repository owns the SCAD capability boundaries, producer
timing context and the content of the SCAD producer log.

## Capability boundary

Persistent producer evidence is attached to the existing domain actions:

| CLI action | Capability | Execution id | Persistent output |
| --- | --- | --- | --- |
| `design-build` | `scad.docs` | `scad-docs` | normal build root |
| `build` | `scad.build` | `scad-build` | normal build root |
| `verify` | `scad.verify` | `scad-verify` | verification output root |

`build-index`, publication/provenance actions and repository-level graph aggregation
are not producer executions merely because an orchestrator exposes them as tasks.

## Persistent producer layout

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
richer domain evidence. Shared Moon capability tasks also supply a producer timing
context, retained as `producer_execution.started_at`, `finished_at` and `duration_ms`.
That timing belongs to the execution that originally produced the retained output.

`execution.log` is intentionally concise. It summarizes producer identity, producer
timing when available and, when structured SCons telemetry exists, the `BUILT`,
`CACHE_RESTORED`, `CURRENT` and `ERROR` decisions. It is not a second copy of raw
OpenSCAD/SCons stdout. Detailed target sources, signatures, cache decisions and other
SCAD-specific facts remain in the structured domain report.

## Producer versus current-run evidence

Producer evidence is part of the cacheable/hydratable producer result. A later
equivalent source revision may hydrate that output without rewriting its producer
`source_revision` or producer timing.

Current-run orchestration evidence is attached only while preparing a publication
snapshot, after Moon execution or hydration:

```text
orchestration/
  run-context.json
  impact-decision.json
  affected-task-ids.json
  scad-ci-plan.json
  moon-invocations/
    <task>/
      materialization.json
      moon.log
```

These files deliberately describe different layers:

- producer `execution.json`: when the retained CAD output was originally produced;
- `moon-invocations/<task>/materialization.json`: when the current source revision
  executed or hydrated that producer result and how long that materialization took;
- `run-context.json`: repository/run identity plus the current publication-family
  snapshot-preparation interval and duration;
- `moon.log`: full current Moon task output, including raw SCons/OpenSCAD producer
  output when the task actually executed.

After hydration it is valid and expected for current materialization/source revision
to differ from the retained producer revision. Publication/finalization must not
rewrite producer evidence to make those revisions appear identical.

## Generated README navigation

Normal Build and Verification publication snapshots expose an evidence map that
distinguishes:

- artifacts;
- producer execution evidence;
- SCAD domain evidence;
- current orchestration/materialization evidence;
- publication context.

The publication staging helper refreshes this map after current orchestration files
exist, so generated output links directly to `run-context.json`, impact/plan evidence,
each task's `materialization.json` and each raw `moon.log`. Evidence is not duplicated
merely to make it easier to find.

## Local and production behavior

A normal local SCAD action can still run outside a Git checkout. If exact producer or
owner revisions cannot be resolved, persistent execution evidence is skipped with a
warning rather than making the CAD action itself Git-only. Producer timing is supplied
by the shared Moon capability wrapper; a direct local CLI invocation may therefore
omit that optional timing object.

Persistent CI/publication consumers are stricter: their acceptance checks must require
the expected `execution.json`/`execution.log` files and validate the common schema.
This makes exact revision evidence mandatory for published snapshots while preserving
local/tool unit-test compatibility.
