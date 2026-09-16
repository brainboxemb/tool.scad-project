# SCAD publication namespaces

## Why this document exists

SCAD uses readable lifecycle concepts such as **Build** and **Verification**, while current-generation repository paths already use compact technical identifiers such as `bld` and `vrf`. Migration 005 originally let persistent publication branches drift to `build` and `verification`, creating two technical names for the same concepts.

This page defines the SCAD-owner application of the portfolio-wide convention in `brainboxemb.meta/docs/working-model/generated-output.md`. Read it when changing publication routing, release branches, cleanup behavior, examples, or consumer configuration.

## Naming contract

Human-facing names remain readable:

```text
Design
Build
Verification
Documentation
```

Stable technical identifiers are:

```text
Design        -> dsg
Build         -> bld
Verification  -> vrf
Documentation -> docs
```

The internal Python/API publication kinds remain `build` and `verification` because those are semantic labels, not branch suffixes.

## Persistent branches

Default current-generation publication is:

```text
pull request #N
  dev/pr-N/bld
  dev/pr-N/vrf

main
  prod/bld
  prod/vrf

release vX.Y.Z
  rel/vX.Y.Z/bld
  rel/vX.Y.Z/vrf
```

Explicit branch overrides in project configuration remain supported for compatibility. Historical branches created under older `build`/`verification` suffixes are retained as historical evidence; current tooling does not rewrite immutable history merely to rename it.

## Workspace roots versus publication kinds

A normal SCAD repository may therefore contain:

```text
dsg/       design source / generated design inputs
bld/       Build output root
vrf/       Verification source/output hierarchy
```

and publish those logical output families to `prod/bld` and `prod/vrf`.

This keeps one technical identifier per shared concept while allowing prose, GitHub job names, release asset labels and other human-facing text to continue using full words where that is clearer.
