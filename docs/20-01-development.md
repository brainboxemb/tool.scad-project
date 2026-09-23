# Development manual

## Start here

Before changing `tool.scad-project`:

1. read [../AGENTS.md](../AGENTS.md);
2. read [10-00-plan.md](10-00-plan.md);
3. identify the affected public SCAD capability/contract;
4. read the matching specification/design detail;
5. inspect the relevant tests and reusable workflow.

## Ownership boundary

Keep implementation in the correct owner:

- generic bootstrap/dependency/repository lifecycle → `tool.git-project`;
- SCAD project/build/design/verification policy → this repository;
- runtime executables/image composition → `docker.scad-toolchain`;
- project geometry/project-specific verification → consumer repository.

## Normal development loop

Use a scoped issue/branch/PR for durable work.

Before merge:

- run focused Python/unit/contract tests for the changed area;
- inspect exact PR-head CI;
- keep reusable workflow self-version expectations consistent;
- update `CHANGELOG.md` for contract-visible changes;
- update the numbered documentation authority rather than duplicating guidance.

After merge, verify the expected exact-main owner workflow.

## Dependencies and version updates

Generic `tool.git-project` calls inside reusable SCAD workflows use an accepted
released generic-tool tag.

The SCAD package/workflow release version is reflected by the package version and
the reusable-workflow self-version markers. Change those only during explicit
release preparation, after current main is qualified.

Consumer `project.yml` selects the semantic `tool.scad-project` release.
The SCAD post-update hook synchronizes SCAD reusable workflow calls to that ref.

## Release preparation

A release is prepared from qualified current main. Keep release-only changes
limited to version/changelog/self-version identity where possible, then qualify
that exact release PR head before creating the immutable tag.

The reusable release flow itself delegates generic tag/release mechanics to
`tool.git-project`.

## Documentation

When changing:

- publication naming → [30-10-publication-namespaces.md](30-10-publication-namespaces.md);
- producer evidence → [30-11-execution-evidence.md](30-11-execution-evidence.md);
- build-decision report contract → [30-12-build-decision-telemetry.md](30-12-build-decision-telemetry.md);
- bootstrap ownership → [40-10-git-bootstrap-boundary.md](40-10-git-bootstrap-boundary.md);
- production orchestration → [40-11-production-workflow.md](40-11-production-workflow.md);
- SCons decision qualification → [50-10-scons-decision-conformance.md](50-10-scons-decision-conformance.md).
