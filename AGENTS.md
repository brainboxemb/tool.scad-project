# Repository agent guidance

This file is for agents changing `tool.scad-project` itself. SCAD consumer
repositories do **not** inherit these instructions.

Before repository work, read the shared BrainboxEmb agent entrypoint:

- [brainboxemb.meta/AGENTS.md](https://github.com/brainboxemb/brainboxemb.meta/blob/main/AGENTS.md)

It owns the current generic Git/commit/PR/CI workflow and routes to the shared
SCAD domain conventions.

## Local technical entrypoints

For durable `tool.scad-project` behavior, start with:

- [README.md](README.md) — consumer-facing architecture, configuration,
  commands, build/design/verification, publication and runtime model;
- [docs/git-bootstrap-boundary.md](docs/git-bootstrap-boundary.md) — boundary
  with `tool.git-project`;
- [docs/production-workflow.md](docs/production-workflow.md) — normal reusable
  production lifecycle;
- [docs/publication-namespaces.md](docs/publication-namespaces.md) — canonical
  Build/Verification publication names;
- [docs/scons-decision-conformance.md](docs/scons-decision-conformance.md) —
  SCons decision contract;
- [docs/build-decision-telemetry.md](docs/build-decision-telemetry.md) and
  [docs/build-decision-audit.md](docs/build-decision-audit.md) — decision
  evidence and audit behavior;
- [docs/execution-evidence.md](docs/execution-evidence.md) — persistent
  execution-evidence contract.

Use source and tests for implementation detail. Use `pyproject.toml`,
`CHANGELOG.md`, release tags and live CI for current release/status evidence.

## Owner boundaries

Keep ownership explicit:

- generic repository/dependency mechanics belong in `tool.git-project`;
- SCAD project policy/orchestration belongs here;
- CAD runtime implementation belongs in `docker.scad-toolchain`;
- project geometry and project-specific verification belong in the consumer.

When changing a public technical contract, update its README/docs/source/tests
authority rather than adding another copy here.

Do not duplicate changing release numbers, roadmap state or portfolio rollout
choices in this file. Cross-project coordination belongs in
`brainboxemb.meta`.

## Consumer boundary

Pinned consumers should reconstruct exact tool behavior from their own
configuration/gitlinks and this pinned revision's README, docs, source and
tests. They should not use this owner `AGENTS.md` as consumer working
guidance.
