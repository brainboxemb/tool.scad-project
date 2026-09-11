# Repository agent guidance

Persistent guidance for automated coding agents working in `tool.scad-project`.

## Purpose

`tool.scad-project` is the reusable project-workflow layer between the shared
runtime and concrete CAD repositories.

```text
docker.scad-toolchain
    runtime / capabilities

tool.scad-project
    reusable workflow / conventions

template.scad-project
    reference consumer
```

Repository name: `tool.scad-project`
CLI name: `scad-project`

## Sources of truth

Do not duplicate changing release numbers in this file.

Use:

```text
pyproject.toml                       tool release version
project.yml in consumers             dependency policy
consumer gitlink                     exact resolved tool commit
consumer workflow refs               reusable workflow release
runtime image + scad-toolchain-info  runtime version/evidence
CHANGELOG.md                          release history
```

When a consumer updates this tool, its `project.yml` ref, gitlink and reusable
workflow refs must move together.

## Configuration-first rule

Project-specific declarations belong in root `project.yml`.

Prefer extending generic configuration/behavior over adding consumer-specific
shell scripts or special-case workflow branches.

## Public architecture boundary

`tool.scad-project` owns policy/orchestration, not runtime implementation and not
project geometry.

```text
docker.scad-toolchain    runtime commands/capabilities
this repository          build/design/dependency/publication orchestration
consumer repository      project configuration, geometry, verification commands
```

Do not duplicate image-processing or CAD runtime implementation that already has
a stable public command in the toolchain.

## Build discovery and engines

Normal consumer render/export targets are discovered from configured roots.
Keep one target-discovery/configuration model shared by all build backends; do
not create a second SCons-only schema.

SCons is an internal optional dependency engine behind the existing
`scad-project build` interface, not a second user-facing build system.

Key rules:

- direct backend remains supported for compatible consumers;
- SCons follows OpenSCAD `use` / `include` transitively;
- literal `import()` / `surface()` files are leaf dependencies;
- unresolved/dynamic file loading must fail safe rather than silently omit a
  dependency;
- configured external-library roots remain dependency search roots even when
  external design documentation is excluded;
- cache signatures must include target specification plus relevant tooling,
  runtime, profile, camera, flag and watermark inputs;
- clean hosted runners may restore valid outputs from persistent SCons cache
  without requiring old `bld/` trees;
- reports should distinguish executed targets from current/restored targets.

Do not replace dependency-aware selection with a broad "nothing changed" cache
shortcut that can miss affected target graphs.

## Generated design documentation

Source `design.md` files are authoritative. Generated documentation/images must
never be written back into project source or external checkouts.

Canonical authoring uses:

```text
scad-render-defaults
scad-render
```

Legacy `scad-design` syntax is compatibility-only.

Generated output lives below:

```text
bld/design/project/...
bld/design/ext/<external-name>/...
```

Build the complete generated tree in staging and replace published/generated
output only after success.

`design.include_externals: false` controls generated documentation only. It must
never remove external CAD source required by project builds.

Design-document caching is separate from per-target SCons selection. Keep the
model understandable; do not add more granular dependency machinery without a
measured need.

## Design render policy

Supported engines are OpenSCAD and PythonSCAD.

Selection precedence:

1. per-render explicit engine;
2. render-default engine;
3. source suffix inference;
4. error if ambiguous.

Explicit engine selection always wins. Do not assume source suffix alone defines
the runtime architecture.

OpenSCAD source views call a source/module/view contract. PythonSCAD source views
inject the selected view and run from the entrypoint directory so sibling Python
imports work naturally.

Inline render snippets remain OpenSCAD-only until an explicit Python inline
format exists.

## Camera/framing rule

Do not emit `$vpr/$vpt/$vpd` into temporary source merely to control generated
design images.

Use CLI camera behavior:

- orientation-only `vpr` can use autocenter/viewall;
- an exact camera requires `vpr`, `vpt` and `vpd` together.

A source-level `$vp*` changes OpenSCAD framing semantics and should not be used as
a hidden workaround for generator behavior.

## OpenSCAD warning policy

Exit code 0 alone is not proof of a valid OpenSCAD build.

Shared command execution must reject warning/error classes that indicate broken
geometry or undefined values while allowing known benign presentation warnings.
Prefer a small explicit allow/fatal policy over treating every warning as fatal.

## Source/API documentation

Use upstream `openscad_docsgen` structured syntax. A structured `.scad` source
must declare `File:` or `LibFile:` before `Module`, `Function`, `Constant`, etc.

Keep API/source documentation and design narrative separate:

```text
.scad docsgen comments    API/source reference
design.md                 design intent / visual construction
```

## Watermark orchestration

The generic PNG operation belongs in `docker.scad-toolchain`; this repository
owns when it is applied according to consumer configuration.

For configured PNG output:

1. render an unwatermarked temporary PNG;
2. invoke public `scad-image-watermark`;
3. verify final output;
4. remove the temporary file.

Do not import Pillow or duplicate watermark drawing here. Do not watermark STL.
Generated design PNGs use the same configured watermark policy as normal build
PNGs; project-specific verification commands should call the same public
watermark command rather than implement their own image processing.

## Dependency policy and commands

`project.yml` is dependency policy; parent gitlinks are the resolved lock.

Supported ref policies include exact stable tag, `latest` stable semantic tag,
and explicit branch. Never interpret `latest` as the default branch.

Keep command semantics distinct:

```text
repo-sync      restore committed locks only
repo-update    intentionally resolve policy and advance locks
repo-status    report policy and locked/current state
```

For configured externals, `deinit` removes the local checkout only; it must not
become repository-level removal equivalent to `git rm`.

Normal consumer checkout is direct-only. Do not recursively initialize a
library's own development dependencies unless a dedicated full-tree integration
test explicitly requires it.

## Bootstrap architecture

Consumers pin this repository at:

```text
tools/tool.scad-project
```

Canonical root helper sources live under `bootstrap/` and are copied into
consumers.

Bootstrap has a hard no-Python requirement. Before the local tool exists, it may
use only Git plus PowerShell/bash to establish/repair the tool gitlink and pinned
checkout.

Bootstrap must be idempotent/recovery-oriented and must fail clearly when
unrelated non-Git content occupies a configured submodule path.

Do not call Python-based `scad-project` commands from the bootstrap step.

After bootstrap, local launchers execute the checked-out source tree directly;
normal project use does not require a network pip install of this package.

Do not rely on `.sh` executable bits in consumer repositories. CI/bootstrap
should invoke shell scripts explicitly with `bash`.

## Reusable workflows

This repository owns the standard reusable build, verify and release workflows.
Consumer repositories should keep thin callers and avoid copying the generic
lint/design/build/publication sequence into local YAML or shell blocks.

`SCAD_PROJECT_WORKFLOW_VERSION`/tooling checks must detect mismatches between
consumer configuration, local tool checkout and reusable workflow release.

## Pull-request-first change workflow

Normal tool and consumer development should start as a draft pull request, not
as an untracked feature branch and not as a direct commit to `main`.

When GitHub supports issue-to-PR conversion, reserve the final pull-request
number before implementation so one identifier is used consistently by the
source branch, pull request and generated preview branches:

```text
issue / draft PR        #N
source branch           feature/pr-N-<short-slug>
preview build           dev/pr-N/build
preview verification    dev/pr-N/verification
```

Canonical sequence:

1. create a temporary issue whose only purpose is to reserve number `N` and
   describe the intended change;
2. create `feature/pr-N-<short-slug>` from the current target branch;
3. make the smallest initial commit required to give the branch a diff;
4. convert **that exact issue `#N`** into a draft pull request using the numbered
   feature branch as its head; do not open a separate pull request, because that
   would consume a different number;
5. continue all implementation as commits on that same branch while the draft PR
   is open, so Build/Verify and review evidence stay attached to the change;
6. mark the PR ready only when the implementation and its generated evidence are
   ready for review;
7. merge only after the required checks and review are complete; PR cleanup owns
   removal of `dev/pr-N/*` and, for same-repository merged PRs, the source branch.

The number in `feature/pr-N-*` is valid only when the reserved issue will be
converted into the same PR. Never guess a future PR number and never use an
unrelated issue number as though it were the PR number.

If issue-to-PR conversion is unavailable or fails, fall back to a descriptive
feature branch plus a normal draft PR. In that fallback, the actual PR number
remains authoritative for `dev/pr-N/*`; do not rename history or fabricate
number alignment merely for aesthetics.

Release-request branches and emergency repository-repair operations are special
workflow mechanisms and are not normal feature development.

This policy is generic to `tool.scad-project` consumers. A consumer root
`AGENTS.md` may add project-specific development or CAD rules, but should defer
to this section for branch/PR/publication workflow and must not contradict it.

## Publication lifecycle

Publication behavior is resolved centrally from source context and consumer
configuration.

General policy:

- `main` / configured production branch -> mutable `prod/build` and
  `prod/verification` snapshots;
- open pull request `#N` -> isolated mutable `dev/pr-N/build` and
  `dev/pr-N/verification` previews;
- ordinary feature-branch pushes without a pull request -> no shared development
  publication under the standard PR-first caller model;
- closing/merging PR `#N` -> remove its `dev/pr-N/*` preview branches and, when
  configured and safe, its same-repository source branch;
- coordinated releases -> immutable release snapshots/tags/bundles according to
  configured release policy.

Every generated snapshot must contain `publication-info.txt` with source,
tooling and runtime provenance. This unified record replaces old
engine-specific build-info files.

`build-index` owns common generated build index content. Consumers should not
hand-maintain competing generated-branch index templates.

Verification orchestration is generic here; actual `verification.commands`
remain project-specific.

## Release workflow for this repository

Use the permanent `.github/workflows/release.yml` path. A release tags an exact,
already-verified commit and then runs the authoritative test workflow on that
immutable ref.

Where the connected GitHub interface cannot invoke workflow dispatch directly,
use the repository's permanent self-cleaning release-request mechanism rather
than creating one-shot workflow files or permanent helper branches.

Never overwrite an existing release tag. A release is accepted only after the
tagged authoritative test run is green.

## Reference consumers

`template.scad-project` is the integration/reference consumer for generic
behavior. Prefer extending that real consumer over creating another test project
unless artificial fixtures would otherwise clutter the template.

For real-world rollout behavior, use the current HUB75 restart repository rather
than the deprecated older display-frame repository.

## Change discipline

When adding or changing generic behavior:

1. keep policy/configuration generic;
2. add unit/integration coverage here;
3. validate against `template.scad-project`;
4. validate against a representative real consumer where appropriate;
5. update documentation without copying volatile versions into `AGENTS.md`.
