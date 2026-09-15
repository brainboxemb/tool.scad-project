# Reusable SCAD production workflow

`project-production.yml` provides the normal repository-level SCAD production lifecycle for current SCAD projects and libraries.

It deliberately keeps three responsibilities separate:

- `tool.git-project` owns Moon/VCS affected-state, the pinned Moon runtime and generated-output publication primitives;
- `tool.scad-project` owns the SCAD production workflow shape and the Build/Verify cache boundaries;
- the consumer repository owns its Moon graph, repository-specific verification and output content.

## Execution model

Normal production uses one GitHub-hosted orchestrator job. The immutable SCAD toolchain remains a container runtime, but it is started explicitly only when Moon says production is required.

```text
one host orchestrator job
  exact HEAD checkout, shallow + blobless
  exact BASE fetched shallowly when available
  no SCAD submodules yet
  Moon affected query against source-impact target
       |
       +-- unaffected --> retain preflight evidence and stop
       |                  no image pull / no SCAD container / no publication
       |
       `-- affected / uncertain
              |
              v
        restore Moon + separate SCons caches on host
        pull immutable SCAD image
        exactly one explicit docker run
          mount the same checked-out worktree
          mount pinned Moon runtime read-only/without GitHub credentials
          bootstrap exact repository dependencies
          explicit MOON_BASE / MOON_HEAD, or MOON_FORCE on uncertainty
          one publication-ready Moon aggregate task
              |
              v
        container exits
        validate current materialization on host
        stage Build + Verification publication trees
        retain prepared artifacts/evidence
        publish both trees sequentially from the same host job
```

The GitHub job/container boundary is not a domain boundary. Build and Verify remain logically independent tasks in the consumer Moon graph even though normal CI executes or hydrates them through one publication-ready aggregate and at most one SCAD container process.

The single-host topology deliberately removes two lifecycle boundaries from the earlier implementation: there is no second production checkout/job and no artifact download hand-off to separate publication jobs. The same exact source worktree is mounted into the SCAD container and then reused by host-side validation and publication after that process exits.

## Affected target versus execution aggregate

Moon correctly treats a configured environment-variable input as affected whenever that variable exists and is non-empty. This matters for publication/index tasks that intentionally include CI context such as `GITHUB_EVENT_NAME` or a pull-request number in their cache inputs. Those tasks should refresh when production runs in a different publication context, but they must not force the expensive SCAD runtime to start for an otherwise unrelated README-only source change.

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

## Minimal checkout and VCS range

The workflow intentionally does not use `fetch-depth: 0`.

It checks out only the exact source/head revision with:

```yaml
fetch-depth: 1
filter: blob:none
submodules: false
persist-credentials: false
```

When a concrete comparison base is available, it fetches only that exact commit with `--depth=1`. The base and head are therefore available as shallow history roots. Migration 004 qualified Moon 2.5.4 against this explicit range model with real consumer revisions; full repository history is not required for the production contract.

The checkout is performed once on the host. If production is affected, that same worktree is mounted into the explicit Docker process. Dependencies are initialized only after the affected gate by the consumer's root `bootstrap.sh`, so an unrelated change never pays SCAD dependency/bootstrap cost.

## Event baselines and conservative execution

The reusable workflow resolves revisions as follows:

- pull request: exact PR head versus exact PR base;
- push: exact current SHA versus `github.event.before`;
- explicit caller overrides: `source_sha` and/or `base_sha`;
- manual/unsupported context without an unambiguous base: missing-base conservative run;
- `force: true`: deliberate conservative run.

A missing, invalid or unfetchable base must never cause a false skip. Released `tool.git-project` affected preflight returns `affected=true` with conservative evidence for uncertainty.

For a concrete base the Docker process receives:

```text
MOON_BASE=<exact comparison base>
MOON_HEAD=<exact source revision>
```

When no usable base exists, preflight has already chosen conservative production. The Docker process then receives `MOON_FORCE=true` and uses the exact source revision for both `MOON_BASE` and `MOON_HEAD`. This intentionally trades affected/cache precision for correctness only in the uncertain case.

## Container and credential boundary

The SCAD image remains immutable:

```text
ghcr.io/brainboxemb/scad-toolchain:<pinned release>
```

The host authenticates only long enough to pull that image and then logs out. The explicit container runs as the host UID/GID and receives the mounted source worktree, Moon runtime and only the CI/provenance variables needed by the consumer graph.

The source checkout uses `persist-credentials: false`, and the GitHub write token is not passed into the SCAD container. Generated-output publication therefore remains a host responsibility after the container exits.

This boundary also prevents root-owned generated output on the host workspace and avoids downloading a second Moon runtime inside the container.

## Cache boundaries

Normal Build and Verification keep separate writable SCons object caches:

```text
.cache/scad-project/scons
.cache/scad-project/verification-scons
```

The host restores those caches before the Docker process and saves newly populated caches afterwards. Restore and save use explicit cache actions/keys so a cold execution can produce a reusable cache snapshot without depending on implicit post-job behavior.

The portable Moon task cache also lives in the host worktree and is mounted into the same aggregate execution. SCons remains authoritative for fine-grained SCAD target decisions when a producer actually executes.

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

The preflight retains `.moon/preflight` as a workflow artifact. Decision evidence names the exact source-impact target, source/base revisions, affected result and conservative reason when applicable.

When production runs, the current aggregate `materialization.json` is validated against the exact source revision before output is staged. Build and Verification publication artifacts each receive the aggregate `moon.log` and `materialization.json` under `orchestration/`; producer/domain evidence remains consumer-owned.

Publication is performed from the same host job through the released `tool.git-project/generated-output/publish` action. It consumes already-prepared trees, does not require OpenSCAD/PythonSCAD, and keeps write credentials outside the SCAD runtime.

Normal publication contexts are same-repository pull requests, the production branch and release tags. Unsupported/manual feature-branch contexts may still produce evidence but do not attempt generated-branch publication.

## Release qualification

Before a topology change to this workflow is released, the reference `template.scad-project` must prove at least:

1. README-only change: source-impact preflight succeeds with `affected=false`; image pull, Docker production and publication are skipped;
2. relevant SCAD/config/tooling change: `affected=true`, exactly one host production job runs and it starts exactly one explicit SCAD Docker process;
3. Build and Verify remain logically independent in the consumer graph and retain separate SCons caches;
4. missing/invalid base runs conservatively instead of skipping and uses forced aggregate execution;
5. aggregate Build/Verify output and current materialization evidence validate before both host-side publications succeed.

Migration 004 retained these scenarios as cross-project evidence rather than keeping temporary proof workflows in the released surface.