# Verification

## Strategy

`tool.scad-project` is a released domain tool with multiple consumer-facing
interfaces: CLI/config behavior, direct and SCons build paths, generated design
documentation, reusable workflows, publication contracts and release behavior.

Verification therefore combines:

- Python/unit contract tests;
- direct/SCons execution tests;
- reusable-workflow policy tests;
- documentation/configuration contract tests;
- exact PR-head and exact-main owner CI;
- exact tag/release qualification for released interfaces.

## Important boundaries to prove

Owner tests should keep proving that:

- generic Git behavior remains delegated to `tool.git-project`;
- direct and SCons consumers retain supported semantics;
- Build and Verification remain separate output domains;
- reusable workflow refs/self-version markers are coherent;
- publication/evidence records identify exact source/tool/runtime context;
- warning/error handling does not treat invalid geometry as success;
- current-generation consumer workflow/config conventions stay synchronized.

## Detailed verification

The deterministic SCons white-box matrix is documented in
[50-10-scons-decision-conformance.md](50-10-scons-decision-conformance.md).

The exact live release gate is defined by current owner workflows/tests rather
than copied as a permanently frozen workflow list here.

## Release evidence

Before creating an immutable tool release:

1. qualify the implementation on exact main;
2. prepare only the required release identity/changelog changes;
3. qualify that exact release PR head;
4. create the release through the established coordinated release flow;
5. verify the tagged/release workflow evidence.
