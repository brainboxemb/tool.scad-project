# Build-decision audit

`scad-project build-audit` checks whether a completed SCons build contains a decision that contradicts changed inputs that can be proven to affect a target.

The audit is deliberately separate from the build itself:

- SCons remains responsible for deciding what to build;
- the existing build-decision report records what happened;
- the audit compares that report with explicit changed paths;
- generic Git/GitHub change discovery remains outside `tool.scad-project`.

## Command

```text
scad-project build-audit \
  --report .cache/scad-project/state/last-build.json \
  --changed-path dsg/openscad/components/corner.scad
```

`--changed-path` may be repeated.

For automation, changed paths can also be read from a newline-delimited file:

```text
scad-project build-audit \
  --report .cache/scad-project/state/last-build.json \
  --changed-paths-file .cache/scad-project/changed-paths.txt
```

Both forms may be combined. Blank lines in a changed-path file are ignored.

The default output is written next to the source report. For example:

```text
.cache/scad-project/state/last-build.json
→ .cache/scad-project/state/last-build-audit.json
```

Use `--output` to choose another location.

## What counts as proven impact?

The existing `scad-project.build-decisions` report already records `sources` for every target. Those entries include the resolved OpenSCAD source/dependency paths known by the build engine.

The first audit version proves impact only when a normalized changed path exactly matches one of those recorded sources.

```text
changed path                  target.sources
---------------------------   ----------------------------------
dsg/components/corner.scad == dsg/components/corner.scad
                              → PROVEN
```

No match becomes `NO_PROVEN_IMPACT`.

That name is intentional: absence of a match does not prove that the target is unaffected. It only means this audit does not have enough evidence to prove impact.

The first version does not use globs, basename guessing or another dependency scanner.

## Decision policy

| Impact | Build outcome | Audit result |
| --- | --- | --- |
| `PROVEN` | `BUILT` | `PASS` |
| `PROVEN` | `CACHE_RESTORED` | `PASS` |
| `PROVEN` | `CURRENT` | `FAIL` |
| `PROVEN` | `ERROR` | `FAIL` |
| `NO_PROVEN_IMPACT` | `CURRENT` | `PASS` |
| `NO_PROVEN_IMPACT` | `CACHE_RESTORED` | `PASS` |
| `NO_PROVEN_IMPACT` | `BUILT` | `WARNING` |
| `NO_PROVEN_IMPACT` | `ERROR` | `FAIL` |

A warning indicates possible overbuild. Warnings do not fail the command in schema version 1.

`CACHE_RESTORED` remains build-decision evidence only. The audit does not independently prove artifact-content integrity.

## Audit report

The command writes a separate machine-readable report:

```text
schema: scad-project.build-decision-audit
schema_version: 1
```

The report contains:

- the source decision-report identity;
- normalized changed paths;
- pass/warning/fail counts;
- overall `PASS` or `FAIL`;
- one audit entry per target.

A target entry contains:

```json
{
  "output": "bld/png/frame.png",
  "outcome": "CURRENT",
  "impact": "PROVEN",
  "matched_changed_sources": [
    "dsg/openscad/components/corner.scad"
  ],
  "audit_result": "FAIL",
  "reason": "PROVEN_LEFT_CURRENT"
}
```

Reason codes are stable machine-readable explanations. The console summary is for humans and is not the API.

## Exit status

The command exits:

- `0` when the report is valid and no target audit is `FAIL`;
- `1` when a proven contradiction, target `ERROR`, malformed report or unsupported report schema is encountered.

For an audit result failure, the JSON audit report is written before exit `1` so the failure evidence remains inspectable.

## Current integration boundary

The audit is an explicit post-build command. `scad-project build` does not invoke it automatically yet because the build command does not own a reliable generic source of changed repository paths.

Automatic change discovery or workflow enforcement belongs in a later integration step once the generic producer of changed-path input is chosen and qualified.

See [`build-decision-telemetry.md`](build-decision-telemetry.md) for the source report contract and [`scons-decision-conformance.md`](scons-decision-conformance.md) for the underlying deterministic SCons behaviour.
