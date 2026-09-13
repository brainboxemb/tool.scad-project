# Structured build-decision telemetry

`tool.scad-project` writes machine-readable SCons decision reports for normal
build targets, generated design images and verification-only targets.

The report contract is shared across all three target classes so downstream
analysis does not need to infer build decisions from console text.

## Reports

The current report files are:

```text
.cache/scad-project/state/last-build.json
.cache/scad-project/state/last-design-build.json
.cache/scad-project/verification-state/last-verification-build.json
```

Each report uses:

```json
{
  "schema": "scad-project.build-decisions",
  "schema_version": 1,
  "manifest_schema_version": 1,
  "kind": "build",
  "engine": "scons",
  "backend_signature": "...",
  "target_count": 1,
  "outcome_counts": {
    "BUILT": 1,
    "CACHE_RESTORED": 0,
    "CURRENT": 0,
    "ERROR": 0
  },
  "targets": []
}
```

`kind` is one of `build`, `design` or `verification`.

## Target outcomes

Every target is classified from the successful-action log plus output existence
immediately before and after SCons runs:

| Action completed | Existed before | Exists after | Outcome |
| --- | --- | --- | --- |
| yes | any | yes | `BUILT` |
| no | no | yes | `CACHE_RESTORED` |
| no | yes | yes | `CURRENT` |
| any unsupported/invalid combination | any | no | `ERROR` |

The important distinction is that `CACHE_RESTORED` and `CURRENT` are not the
same event. A fresh design staging tree, for example, can materialize an
unchanged image from SCons `CacheDir`; that target is `CACHE_RESTORED`. An
already-present normal build output that SCons leaves untouched is `CURRENT`.

A target entry contains:

```json
{
  "output": "bld/png/example.png",
  "outcome": "BUILT",
  "action_executed": true,
  "existed_before": false,
  "exists_after": true,
  "sources": [
    "dsg/openscad/render/example.scad",
    "dsg/openscad/components/shared.scad"
  ],
  "target_spec_digest": "..."
}
```

`sources` records the source/dependency inputs known to the target compiler.
`target_spec_digest` is a stable SHA-256 digest of the target specification and
intentionally excludes the runtime-only `existed_before` observation.

The same runtime-only field is excluded from the SCons `Value()` signature so
telemetry cannot invalidate an otherwise unchanged CAD target merely because an
output now exists.

## Provenance

Reports record the provenance available in the execution environment:

```json
{
  "provenance": {
    "source_commit_sha": "...",
    "tool_version": "...",
    "tool_commit_sha": "...",
    "toolchain_image": "...",
    "toolchain_version": "...",
    "workflow_version": "...",
    "cache": {
      "namespace": "...",
      "primary_key": "...",
      "matched_key": "...",
      "exact_hit": false
    }
  }
}
```

The reusable Build/Verify workflows provide exact tool SHA and the relevant
GitHub Actions cache context. Local CLI runs may leave workflow-only provenance
fields empty; this does not change target classification.

In Verify, the normal configured-build report receives normal selective-build
cache context. Before verification-only targets run, the workflow switches the
context to the separate verification cache namespace.

## GitHub Actions evidence

Reusable Build uploads normal and design decision reports when present. Reusable
Verify uploads the normal configured-build report and the verification-only
report when present.

The Step Summary uses the same four outcome names as the JSON:

```text
BUILT | CACHE_RESTORED | CURRENT | ERROR
```

The exact generated-design snapshot remains a separate GitHub Actions cache
optimization. If that exact snapshot is restored, design SCons is skipped and
there is no new per-target design decision report for that run; the Step Summary
states that explicitly instead of pretending the snapshot restore was a SCons
target outcome.

## Scope boundary

This telemetry contract is Step 1 of the cross-project tooling plan in
`meta.scad-projects`.

It provides evidence only. The deterministic SCons decision matrix belongs to
Step 2, and policy that compares expected versus actual rebuilds belongs to the
post-build audit in Step 3. Those later concerns must not be embedded in this
report writer.
