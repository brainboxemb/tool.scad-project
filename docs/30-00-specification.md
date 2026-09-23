# Specification

## Why this tool exists

SCAD repositories need consistent project configuration, build/design/
verification semantics, reusable CI workflows and publication behavior without
copying those mechanics into every CAD repository.

`tool.scad-project` owns that SCAD-domain contract.

## Typical users

Primary users are:

- maintainers of current-generation SCAD projects and libraries;
- reusable SCAD libraries that need consistent build/verification tooling;
- CI workflows invoking released SCAD lifecycle contracts.

## Why use it

Use this tool when a repository needs one or more of:

- OpenSCAD/PythonSCAD build/export/render orchestration;
- generated design documentation;
- independent Verification output;
- direct or SCons-backed target execution;
- shared SCAD Moon capability policy;
- released SCAD production/release workflows;
- stable SCAD publication/evidence contracts.

## Non-goals

The tool does not own:

- generic Git dependency/bootstrap semantics;
- Moon's scheduler/hasher/cache implementation;
- runtime-image implementation;
- project geometry/design decisions;
- product-specific verification;
- arbitrary drawing/layout policy beyond the declared project producer contract.

## Public contract details

- [30-10 — Publication namespaces](30-10-publication-namespaces.md)
- [30-11 — Execution evidence](30-11-execution-evidence.md)
- [30-12 — Build-decision telemetry](30-12-build-decision-telemetry.md)

Practical commands live under [20 manuals](20-00-manuals.md). Ownership and
production architecture live under [40 design](40-00-design.md).
