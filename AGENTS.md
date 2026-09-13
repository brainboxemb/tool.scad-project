# Repository agent guidance

Persistent guidance for automated coding agents working in `tool.scad-project`.

## Purpose

`tool.scad-project` is the reusable SCAD project/build layer between generic
repository tooling, the shared CAD runtime and concrete SCAD consumers.

```text
tool.git-project
    generic Git bootstrap / dependencies

        ↓

tool.scad-project
    SCAD configuration / build / design / verification / workflows

        ↓

docker.scad-toolchain
    runtime / external capabilities
```

Repository name: `tool.scad-project`
CLI name: `scad-project`

## Ownership boundary

Generic Git repository management does **not** belong here.

`tool.git-project` owns:

- bootstrap of the pinned generic tool gitlink;
- generic `project.yml` parsing/validation;
- dependency/submodule registration;
- dependency ref resolution and checkout;
- dependency status and controlled update;
- dirty-dependency protection.

This repository owns:

- `project.scad.yml` interpretation;
- OpenSCAD/PythonSCAD project policy;
- build target discovery;
- SCons dependency-aware execution;
- design documentation generation;
- verification target orchestration;
- SCAD-specific publication/release behavior;
- reusable SCAD GitHub Actions workflows;
- exact-SHA alignment of consumer calls to those SCAD workflows.

Do not add another Git-submodule parser, `latest` resolver, bootstrap engine or
generic dependency updater here. Compatibility commands may delegate to the
pinned `tool.git-project`; they must not reimplement it.

## Configuration split

The current-generation consumer model is:

```text
tools/tool.git-project       bootstrap engine, pinned directly by Git
project.yml                  generic project/profile/dependency policy
project.scad.yml             SCAD-specific configuration
tools/tool.scad-project      managed dependency
```

`project.yml` declares the SCAD profile and managed dependencies. The SCAD
loader composes the generic project name/tool dependency/external dependency
locations with SCAD-only profile data.

The legacy combined `project.yml` remains a compatibility input. New and migrated
current-generation consumers use the split model. Removing the compatibility
path is a later cleanup/release decision.

SCAD-only metadata for an external (for example `required_file`) may live in the
SCAD profile keyed by dependency name. URL/path/ref/type remain generic
dependency policy in `project.yml`.

## Generic repository command bridge

`scad-project repo-sync`, `repo-update` and `repo-status` are compatibility /
composition commands. They invoke `tool.git-project` for the generic operation.

After an update, SCAD-specific workflow callers still need to match the exact
checked-out `tool.scad-project` commit. That is owned here because these reusable
workflow names are part of the SCAD tool API:

```text
project-build.yml
project-verify.yml
project-release.yml
```

`scad-project workflow-sync` performs that exact-SHA rewrite. `repo-update`
runs generic update first, then workflow sync.

Consumer `update-repo.*` helpers must stay tiny and call the SCAD composition
command; they must not contain their own dependency parser/resolver.

## Sources of truth

Do not duplicate changing release numbers in this file.

Use:

```text
pyproject.toml                       tool release version
consumer project.yml                generic dependency policy
consumer project.scad.yml           SCAD-specific policy
consumer gitlinks                   exact resolved dependency commits
consumer workflow refs              exact reusable-workflow tool commit
runtime image + scad-toolchain-info  runtime version/evidence
CHANGELOG.md                          release history
```

## Public architecture boundary

`tool.scad-project` owns policy/orchestration, not runtime implementation and
not project geometry.

```text
tool.git-project          generic repository/dependency operations
docker.scad-toolchain     runtime commands/capabilities
this repository           SCAD build/design/verification/workflow orchestration
consumer repository       project configuration, geometry, project checks
```

Do not duplicate image-processing or CAD runtime implementation that already
has a stable public command in the toolchain.

## Build discovery and engines

Normal consumer render/export targets are discovered from configured roots.
Keep one target-discovery/configuration model shared by all build backends; do
not create a second SCons-only schema.

SCons is an internal dependency engine behind the existing `scad-project build`
interface, not a second user-facing build system.

Key rules:

- direct backend remains supported for compatible consumers;
- SCons follows OpenSCAD `use` / `include` transitively;
- literal `import()` / `surface()` files are leaf dependencies;
- unresolved/dynamic file loading must fail safe rather than silently omit a
  dependency;
- configured external-library roots remain dependency search roots;
- cache signatures include target specification plus relevant tooling/runtime
  and render-policy inputs;
- structured SCons reports use the shared target outcomes `BUILT`,
  `CACHE_RESTORED`, `CURRENT` and `ERROR` for normal, design and verification
  targets.

Meta Step 0.5 is complete. Issue/PR #38 is the active Step 1 implementation for
structured decision telemetry. Do not fold the Step 2 deterministic SCons matrix,
Step 3 audit policy or later roadmap work into Step 1 merely because the report
schema now makes those later steps possible.

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

## Design render policy

Supported engines are OpenSCAD and PythonSCAD.

Selection precedence:

1. per-render explicit engine;
2. render-default engine;
3. source suffix inference;
4. error if ambiguous.

Explicit engine selection always wins.

Do not emit `$vpr/$vpt/$vpd` into temporary source merely to control generated
design images. Use CLI camera behavior: orientation-only `vpr` may use
autocenter/viewall; exact camera requires `vpr`, `vpt` and `vpd` together.

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

## Reusable workflows

This repository owns the standard reusable Build, Verify and Release workflows.
Consumer repositories should keep thin callers and avoid copying the generic
lint/design/build/publication sequence into local YAML or shell blocks.

Reusable workflow calls from consumers must be pinned to the exact checked-out
`tool.scad-project` commit. `workflow-sync` is the SCAD-specific mechanism that
keeps those callers aligned after `tool.git-project` changes the tool gitlink.

`SCAD_PROJECT_WORKFLOW_VERSION` remains release/provenance evidence; it is not a
replacement for the exact workflow caller SHA.

## Pull-request-first change workflow

Normal development starts as a draft pull request.

When possible:

1. create a temporary issue to reserve number `N`;
2. create `feature/pr-N-<short-slug>` from current target branch;
3. make the smallest initial commit;
4. convert that exact issue into draft PR `#N`;
5. continue implementation on the same branch;
6. mark ready only when implementation/evidence are reviewable;
7. merge only after required checks/review.

Generated PR previews use `dev/pr-N/build` and `dev/pr-N/verification`.
Never guess a future PR number or reuse an unrelated issue number.

## Publication lifecycle

General policy:

- `main` / configured production branch -> mutable `prod/build` and
  `prod/verification` snapshots;
- open pull request `#N` -> isolated mutable `dev/pr-N/build` and
  `dev/pr-N/verification` previews;
- ordinary feature-branch pushes -> no shared development publication by
  default;
- coordinated releases -> immutable release snapshots/tags/bundles.

Every generated snapshot contains `publication-info.txt` with source, tooling
and runtime provenance.

## Reference consumers

`template.scad-project` is the first integration/reference consumer for generic
SCAD behavior. For broader rollout, use the current-generation classification
from `tech.scad`; do not silently migrate classic CAD projects.

For real-world current-stack behavior, use the current HUB75 restart repository,
not the deprecated older display-frame project.

## Change discipline

When adding or changing generic SCAD behavior:

1. keep generic Git behavior in `tool.git-project`;
2. keep SCAD policy/configuration generic across SCAD consumers;
3. add unit/integration coverage here;
4. validate against `template.scad-project`;
5. validate against a representative current consumer where appropriate;
6. update meta cross-project evidence without copying volatile implementation
   details there.
