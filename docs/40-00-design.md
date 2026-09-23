# Design

## Ownership layers

```text
consumer SCAD repository
        |
        +-- tool.git-project
        |     generic bootstrap / dependency / Moon host mechanics /
        |     generated-output publication / generic release mechanics
        |
        +-- tool.scad-project
        |     SCAD config / build / design / verification /
        |     runtime selection / reusable SCAD workflows
        |
        +-- docker.scad-toolchain
              OpenSCAD / PythonSCAD / SCons / drawing executables
```

Each layer owns only the semantics it can define generically at that level.

## Consumer update boundary

Root `bootstrap.*` and `update.*` launchers are generic managed files from
`tool.git-project`.

After generic dependency movement, `tool.scad-project` may run its small
post-update hook to synchronize SCAD reusable-workflow refs. It does not own a
second root updater.

See [40-10 — Git bootstrap boundary](40-10-git-bootstrap-boundary.md).

## Production architecture

Normal SCAD CI uses coarse visible capabilities (`scad.docs`, `scad.build`,
`scad.verify`) while SCons remains authoritative for fine-grained CAD target
decisions inside a capability.

See [40-11 — Production workflow](40-11-production-workflow.md).

## Evidence boundary

The SCAD tool produces SCAD/SCons domain telemetry and wraps producer executions
in the generic execution-evidence contract owned by `tool.git-project`.

Exact consumer-facing evidence contracts belong in the specification family.
