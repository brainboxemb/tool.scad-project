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
  Moon affected query against source-impact target
       |
       +-- unaffected --> stop
       |
       `-- affected / uncertain
              |
              v
        one SCAD production job
          fresh exact HEAD, shallow + blobless
          exact BASE fetched shallowly for Moon run context
          explicit MOON_BASE / MOON_HEAD
          bootstrap exact repository dependencies
          separate Build SCons cache
          separate Verify SCons cache
          one publication-ready Moon aggregate task
          validate current materialization
          stage Build + Verification publication trees
              |
              v
        lightweight host publication jobs
```

The GitHub job/container boundary is not a domain boundary. Build and Verify remain logically independent tasks in the consumer Moon graph even though normal CI can execute or hydrate them inside one heavy job.

## Affected target versus execution aggregate

Moon correctly treats a configured environment-variable input as affected whenever that variable exists and is non-empty. This matters for publication/index tasks that intentionally include CI context such as `GITHUB_EVENT_NAME` or a pull-request number in their cache inputs. Those tasks should refresh when production runs in a different publication context, but they must not force the expensive SCAD container to start for an otherwise unrelated README-only source change.

The workflow therefore supports two Moon targets with different responsibilities:

- `affected_task`: optional source-impact target used only by the host-side preflight;
- `aggregate_task`: publication-ready execution target run inside the SCAD container when production is required.

When `affected_task` is omitted it defaults to `aggregate_task`, preserving the simple contract for consumers whose aggregate contains no always-defined environment inputs.

For SCAD consumers that have environment-sensitive index/provenance tasks, the recommended graph is:

```text
scad.production-impact
    depends on producer-domain tasks only
    e.g. scad.docs + scad.build + scad.verify

scad.ci
    depends on publication-ready branches
    e.g. scad.build-provenance + scad.verification-provenance
```

This is still entirely Moon-native affected analysis. It does not add a second changed-path model or duplicate file filters in GitHub Actions; the consumer Moon graph remains the authority for what source changes require heavy production.

## Minimal preflight checkout

The preflight intentionally does not use `fetch-depth: 0`.

It checks out only the exact source/head revision with:

```yaml
fetch-depth: 1
filter: blob:none
submodules: false
```

When a concrete comparison base is available, it fetches only that exact commit with `--depth=1`. The base and head are therefore available as shallow history roots; intermediate ancestry is not required for Moon's explicit `base -> head` changed-file query.

Migration 004 qualified this behavior against Moon 2.5.4 with real `template.scad-project` revisions. Retained run `34895987723` proves a normal successful affected decision when both exact commits are shallow roots and intermediate history is not traversable. The temporary proof workflow used for that qualification is deliberately not part of the released production surface.

## Event baselines

The reusable workflow resolves revisions as follows:

- pull request: exact PR head versus exact PR base;
- push: exact current SHA versus `github.event.before`;
- explicit caller overrides: `source_sha` and/or `base_sha`;
- manual/unsupported context without an unambiguous base: missing-base conservative run;
- `force: true`: deliberate conservative run.

A missing, invalid or unfetchable base must never cause a false skip. The released `tool.git-project` Moon preflight returns `affected=true` for uncertainty.

## Production checkout and Moon VCS context

The heavy SCAD job performs a fresh exact source checkout. It does not inherit the preflight worktree or its Git history.

Moon also uses VCS context while executing and hashing normal tasks, even when the requested aggregate target is not invoked with `--affected`. A detached one-commit source checkout alone is therefore insufficient because the workspace default branch is not locally resolvable.

For a concrete comparison base, the production job independently fetches only that exact base commit with `--depth=1` and exports:

```text
MOON_BASE=<exact comparison base>
MOON_HEAD=<exact source revision>
```

This gives the normal Moon run the same explicit revision range as the preflight without introducing full history, a synthetic branch, or a second VCS decision model.

When no usable base exists, preflight already chose conservative production. In that case the production job exports `MOON_FORCE=true` and sets `MOON_BASE` and `MOON_HEAD` to the exact source revision so Moon executes without relying on an unavailable default-branch comparison. This intentionally trades cache reuse for correctness only in the uncertain case.

Submodules/dependencies are initialized only after the affected gate by the consumer's root `bootstrap.sh`. This preserves the generic repository bootstrap ownership of `tool.git-project` and avoids paying dependency setup for unaffected changes.

## Cache boundaries

Normal Build and Verification keep separate writable SCons object caches:

```text
.cache/scad-project/scons
.cache/scad-project/verification-scons
```

The workflow also uses the released `tool.git-project/moon` action for the repository-level Moon cache/materialization layer. SCons remains authoritative for fine-grained SCAD target decisions when a producer executes.

## Consumer contract

A consumer supplies a publication-ready Moon aggregate task, normally `consumer:scad.ci`, whose graph owns the final Build and Verify publication branches. Consumers may additionally supply a source-impact target when publication metadata has environment-sensitive inputs.

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
      affected_task: consumer:scad.production-impact
      aggregate_task: consumer:scad.ci
      cache_namespace: my-repository-scad-production-v1
```

The caller must pin the reusable workflow to the exact checked-out `tool.scad-project` commit. `scad-project workflow-sync` maintains that alignment.

## Evidence and publication

The preflight retains `.moon/preflight` as a workflow artifact. The decision evidence names the exact source-impact target that Moon evaluated. When production runs, Moon materialization evidence for the execution aggregate is validated against the exact source revision before output is staged.

Build and Verification publication artifacts each receive the current aggregate `moon.log` and `materialization.json` under `orchestration/`. The actual generated content and producer/domain evidence remain consumer/producer-owned.

Publication is delegated to the lightweight generated-output workflow in released `tool.git-project`; OpenSCAD/PythonSCAD is not required to publish already-prepared output.

## Release qualification

Before this workflow is released, the reference `template.scad-project` must prove at least:

1. README-only change: source-impact preflight succeeds with `affected=false` and no SCAD container job starts;
2. relevant SCAD/config/tooling change: `affected=true` and exactly one normal SCAD container starts;
3. verification-only impact still preserves Build/Verify logical independence;
4. missing/invalid base runs conservatively instead of skipping;
5. aggregate Build/Verify output, current materialization evidence and lightweight publication remain valid.
