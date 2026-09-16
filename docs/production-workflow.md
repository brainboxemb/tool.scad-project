# Reusable SCAD production workflow

`project-production.yml` is the normal repository-level SCAD lifecycle for Migration 005 consumers.

The maintainer-facing model is deliberately capability-oriented. A consumer exposes only the SCAD capabilities it actually has:

```text
scad.docs    design documentation
scad.build   presentation renders/exports
scad.verify  verification
```

Generic lifecycle mechanics are not extra Moon capabilities.

## Responsibility split

```text
GitHub Actions
  exact source/base, credentials, hosted runner
        |
        v
Moon on the host
  one affected-task query
        |
        +-- no affected SCAD capability -> stop
        |
        v
SCAD-owned execution plan
  validate Moon capabilities against project.scad.yml
  select runtime profile and applicable caches
        |
        v
one SCAD Docker process
  execute/hydrate required Moon capabilities
        |
        v
host finishing/publication
  current source/run/publication information
  compact orchestration evidence
  changed Build/Verification publication families
```

`tool.git-project` owns the Moon runtime, VCS change query and generic generated-output publisher. `tool.scad-project` owns the shared SCAD capability policy, project/configuration consistency, runtime/cache selection and finishing workflow. The consumer owns project-specific capability inputs, exceptional output overrides and domain verification commands.

## Shared Moon capability policy

The standard capability definitions live in pinned `tools/tool.scad-project/moon/tasks/scad.yml` and are inherited with native Moon configuration. A consumer links the shared task file once and selects the capabilities it exposes through `workspace.inheritedTasks.include` in the project-level root `moon.yml`.

Conceptually:

```yaml
# .moon/tasks/scad.yml
extends: '../../tools/tool.scad-project/moon/tasks/scad.yml'
```

```yaml
# moon.yml
workspace:
  inheritedTasks:
    include:
      - scad.docs
      - scad.verify
```

`.moon/workspace.yml` remains workspace-level configuration such as project registration. The consumer root `moon.yml` contains the project-level capability selection plus only project-specific input additions and exceptional output overrides. It does not copy commands, common tool inputs, cache policy, provenance tasks or lifecycle aggregate roots.

`project.scad.yml` remains the SCAD-domain project model. The SCAD planner rejects contradictions between the visible Moon capability set and the project configuration.

## One impact query

The workflow checks out the exact source revision shallow/blobless and fetches only the exact comparison-base commit when available. It then calls released `tool.git-project v0.2.8` once.

That action asks Moon for the complete affected-task set for `base -> head`. Migration 005 consumes the returned task list instead of reducing the result to one boolean.

The current v0.2.8 interface still requires one existing Moon task as a query anchor. The production workflow uses `consumer:scad.docs`; the reference/template rollout therefore requires `scad.docs`. The complete affected-task list itself is not limited to that task: build- or verification-only changes are still present in the same Moon query result. A future generic affected interface may remove the anchor requirement; it must not reintroduce a second changed-path model in this workflow.

A missing/unusable base or Moon-query failure is conservative: the configured SCAD capability set is treated as required rather than risking a false skip.

## Unaffected path

If the complete affected-task list contains no configured SCAD capability, normal production stops on the host.

That path intentionally performs:

```text
SCAD image pulls     0
SCAD Docker starts   0
CAD work             0
SCons cache actions  0
```

Only compact impact evidence is retained.

## SCAD-owned execution plan

Only when Moon reports possible SCAD work does the host initialize the exact pinned `tool.scad-project` dependency and run the SCAD planner.

The planner derives and validates:

- configured capability set;
- affected capability set;
- publication-safe materialization scope;
- OpenSCAD-focused versus full/dual runtime profile;
- direct versus SCons build engine;
- whether the normal SCons cache is applicable;
- whether a real Verification-SCons target engine exists;
- Build and Verification output roots.

Runtime selection is based on project intent, never repository names:

```text
OpenSCAD-only -> ghcr.io/brainboxemb/scad-toolchain-openscad:v0.5.0
PythonSCAD configured -> ghcr.io/brainboxemb/scad-toolchain:v0.5.0
```

## Affected work versus publication-safe materialization

`affected_capabilities` and `materialization_capabilities` are intentionally different concepts.

For example, `scad.docs` and `scad.build` both contribute to one complete Build publication tree. On a fresh runner, a docs-only change cannot safely publish a tree containing only `bld/design` because replacing the generated Build branch would delete unchanged presentation output.

Therefore:

```text
affected:        scad.docs
materialization: scad.docs + scad.build   (when both are configured)
publish family:  Build
```

The unchanged contributor normally hydrates from Moon's whole-capability cache. If that cache entry is missing, Moon may safely reproduce the contributor. This is publication correctness, not a claim that the contributor was source-affected.

Verification is a separate publication family and is never pulled into Build merely for completeness.

## One runtime process

All required capability materialization happens inside one explicit Docker process on one hosted runner. Each capability is invoked separately through released `tool.git-project v0.2.8` Moon tooling so Moon can execute or hydrate it independently.

The container receives no GitHub write credential. Source checkout uses `persist-credentials: false`; generated-output publication stays on the host after the runtime exits.

`PYTHONDONTWRITEBYTECODE=1` is set for production. Generated Python bytecode must not contaminate source-derived Moon input identity.

## Cache boundaries

### Moon

Moon is the whole-capability cache/reuse layer. The host transports only Moon's portable hash/output cache directories.

### SCons

SCons remains optional fine-grained target reuse inside configured capabilities.

The normal cache is transported only when:

```text
build_engine.engine == scons
and scad.docs/scad.build is configured
```

The separate Verification cache is transported only when:

```text
build_engine.engine == scons
and scad.verify is configured
and verification.render_root/export_root exists
```

A verification command by itself does not justify a Verification-SCons cache. A direct-engine project performs no SCons cache restore/save merely because SCons exists in the runtime image.

## Source-derived output versus current-run information

Shared Moon capabilities contain only source/tool/config-derived work and producer evidence. GitHub run id, PR number, current ref and publication destination do not define their cache identity.

After Moon execution/hydration, the host adds truthful current-run finishing information:

- `build-index` for Build publication;
- Build or Verification `publication-info.txt`;
- impact decision and affected-task evidence;
- current Moon materialization evidence.

Cached producer evidence intentionally continues to identify the execution that originally produced the reusable output.

## Normal artifact and publication policy

Normal production does not upload complete Build and Verification trees again as GitHub Actions artifacts. Those trees are already available through generated-output branches and same-job publication consumes local staging directly.

Normal CI retains one compact evidence artifact containing impact/planning/orchestration evidence.

Build and Verification publishers are isolated `tool.git-project` processes. When both output families changed, the workflow starts both publishers on the same host and waits for both results. This overlaps network finishing without adding another hosted runner.

Only changed output families are published:

```text
docs/build change -> Build publication
verification change -> Verification publication
both -> both, concurrently on the same host
```

## Release remains different

The coordinated release workflow deliberately retains separate preflight, Build, Verify and finalize jobs. Its complete Build and Verification artifacts are real cross-job hand-off and remain mandatory.

Release preflight uses the same SCAD planner to derive:

- runtime image;
- normal SCons cache applicability;
- Verification-SCons cache applicability.

Those decisions are passed explicitly into the release Build/Verify reusable workflows. Release-request parsing/validation and request-branch cleanup are owned by the shared release workflow as well, so consumers do not duplicate that shell orchestration. Release does not use the normal-CI artifact-retention policy.

## Thin consumer callers

The normal caller no longer supplies aggregate/affected Moon tasks or duplicated output-root policy. A typical caller is:

```yaml
jobs:
  scad:
    permissions:
      contents: write
      packages: read
    uses: brainboxemb/tool.scad-project/.github/workflows/project-production.yml@v0.14.x
    with:
      cache_namespace: my-repository-scad-production-v2
```

The coordinated release caller is similarly thin:

```yaml
jobs:
  release:
    permissions:
      actions: read
      contents: write
      packages: read
    uses: brainboxemb/tool.scad-project/.github/workflows/project-release.yml@v0.14.x
```

The semantic reusable-workflow ref must match the configured `tool.scad-project` release ref in `project.yml`; `scad-project workflow-sync` maintains that alignment. The parent repository gitlink remains the exact resolved commit for the release, so readability and exact source identity have separate, non-duplicated roles.

## Qualification expectations

Before a release of this lifecycle, owner tests plus reference-consumer evidence must prove at least:

1. unrelated/README-only change starts no SCAD runtime;
2. one affected capability is identified from the one Moon query;
3. multiple affected capabilities remain distinguishable;
4. conservative failure runs the configured capability scope safely;
5. Moon can hydrate unchanged whole capabilities;
6. direct projects perform no SCons transport;
7. SCons projects retain only useful SCons cache paths;
8. OpenSCAD-only and full/dual projects select the correct v0.5.0 image;
9. complete normal Build/Verification Actions artifacts are not duplicated;
10. same-host Build/Verification publication remains isolated and correct;
11. the coordinated release artifact hand-off still works;
12. consumer production/release callers remain on the same released semantic tool ref as `project.yml`.
