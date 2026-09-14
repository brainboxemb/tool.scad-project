# Reusable SCAD production workflow

`project-production.yml` provides the normal repository-level SCAD production lifecycle for current SCAD projects and libraries.

It deliberately keeps three responsibilities separate:

- `tool.git-project` owns Moon/VCS affected-state and portable Moon task execution;
- `tool.scad-project` owns the SCAD production workflow shape and the Build/Verify cache boundaries;
- the consumer repository owns its Moon graph, repository-specific verification and output content.

## Execution model

```text
host preflight
  exact HEAD, shallow + blobless
  exact BASE, fetched shallowly
  no SCAD submodules
  no SCAD container
  Moon affected query
       |
       +-- unaffected --> stop
       |
       `-- affected / uncertain
              |
              v
        one SCAD production job
          exact HEAD, shallow + blobless
          bootstrap exact repository dependencies
          separate Build SCons cache
          separate Verify SCons cache
          one Moon aggregate task
          validate current materialization
          stage Build + Verification publication trees
              |
              v
        lightweight host publication jobs
```

The GitHub job/container boundary is not a domain boundary. Build and Verify remain logically independent tasks in the consumer Moon graph even though normal CI can execute or hydrate them inside one heavy job.

## Minimal preflight checkout

The preflight intentionally does not use `fetch-depth: 0`.

It checks out only the exact source/head revision with:

```yaml
fetch-depth: 1
filter: blob:none
submodules: false
```

When a concrete comparison base is available, it fetches only that exact commit with `--depth=1`. The base and head are therefore available as shallow history roots; intermediate ancestry is not required for Moon's explicit `base -> head` changed-file query.

The repository contains a Migration-004 proof workflow while this behavior is being qualified against Moon 2.5.4. That proof uses real `template.scad-project` commits and requires a normal successful `task-affected` decision rather than accepting the conservative fallback.

## Event baselines

The reusable workflow resolves revisions as follows:

- pull request: exact PR head versus exact PR base;
- push: exact current SHA versus `github.event.before`;
- explicit caller overrides: `source_sha` and/or `base_sha`;
- manual/unsupported context without an unambiguous base: missing-base conservative run;
- `force: true`: deliberate conservative run.

A missing, invalid or unfetchable base must never cause a false skip. The released `tool.git-project` Moon preflight returns `affected=true` for uncertainty.

## Production checkout

The heavy SCAD job performs a fresh exact source checkout. It does not inherit or refetch the preflight history.

Submodules/dependencies are initialized only after the affected gate by the consumer's root `bootstrap.sh`. This preserves the generic repository bootstrap ownership of `tool.git-project` and avoids paying dependency setup for unaffected changes.

## Cache boundaries

Normal Build and Verification keep separate writable SCons object caches:

```text
.cache/scad-project/scons
.cache/scad-project/verification-scons
```

The workflow also uses the released `tool.git-project/moon` action for the repository-level Moon cache/materialization layer. SCons remains authoritative for fine-grained SCAD target decisions when a producer executes.

## Consumer contract

A consumer supplies a Moon aggregate task, normally `consumer:scad.ci`, whose graph owns the real Build and Verify dependencies. The workflow does not encode project-specific filenames or geometry expectations.

Default publication roots are:

```text
Build:        bld
Verification: vrf/out
```

They can be overridden for a repository with a different established layout.

A thin caller can use:

```yaml
jobs:
  scad:
    permissions:
      contents: write
      packages: read
    uses: brainboxemb/tool.scad-project/.github/workflows/project-production.yml@<exact-tool-commit>
    with:
      aggregate_task: consumer:scad.ci
      cache_namespace: my-repository-scad-production-v1
```

The caller must pin the reusable workflow to the exact checked-out `tool.scad-project` commit. `scad-project workflow-sync` maintains that alignment.

## Evidence and publication

The preflight retains `.moon/preflight` as a workflow artifact. When production runs, Moon materialization evidence for the aggregate task is validated against the exact source revision before output is staged.

Build and Verification publication artifacts each receive the current aggregate `moon.log` and `materialization.json` under `orchestration/`. The actual generated content and producer/domain evidence remain consumer/producer-owned.

Publication is delegated to the lightweight generated-output workflow in released `tool.git-project`; OpenSCAD/PythonSCAD is not required to publish already-prepared output.

## Release qualification

Before this workflow is released, the reference `template.scad-project` must prove at least:

1. README-only change: preflight succeeds with `affected=false` and no SCAD container job starts;
2. relevant SCAD/config/tooling change: `affected=true` and exactly one normal SCAD container starts;
3. verification-only impact still preserves Build/Verify logical independence;
4. missing/invalid base runs conservatively instead of skipping;
5. aggregate Build/Verify output, current materialization evidence and lightweight publication remain valid.
