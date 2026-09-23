# Repository agent guidance

This file is for agents changing `tool.scad-project` itself. SCAD consumer
repositories do **not** inherit these instructions.

Before repository work, read the shared BrainboxEmb agent entrypoint:

- [brainboxemb.meta/AGENTS.md](https://github.com/brainboxemb/brainboxemb.meta/blob/main/AGENTS.md)

It owns the current generic Git/commit/PR/CI workflow and routes to the shared
SCAD domain conventions.

## Local technical entrypoints

For durable `tool.scad-project` behavior, start with:

- [README.md](README.md) — GitHub-facing consumer orientation;
- [docs/README.md](docs/README.md) — documentation index;
- [docs/10-00-plan.md](docs/10-00-plan.md) — current owner work;
- [docs/20-01-development.md](docs/20-01-development.md) — contributor/release workflow;
- [docs/20-02-user.md](docs/20-02-user.md) — consumer operating guide;
- [docs/30-00-specification.md](docs/30-00-specification.md) — supported SCAD contracts;
- [docs/40-00-design.md](docs/40-00-design.md) — ownership and architecture;
- [docs/50-00-verification.md](docs/50-00-verification.md) — qualification strategy.

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
