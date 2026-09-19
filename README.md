# tool.scad-project

Reusable SCAD project tooling for OpenSCAD/PythonSCAD build, design documentation,
verification, publication and release workflows.

## Architecture

`tool.scad-project` owns SCAD-domain configuration, commands, shared Moon capability
policy and reusable GitHub workflows. Generic repository bootstrap, Moon/VCS query
mechanics and generated-output publication primitives belong to
[`tool.git-project`](https://github.com/brainboxemb/tool.git-project).

```text
consumer repository
    |
    +-- tools/tool.git-project
    |      generic bootstrap / Moon / generated-output publication
    |
    +-- project.yml
    |      generic project + dependency policy
    |
    +-- project.scad.yml
    |      SCAD build/design/verification/publication intent
    |
    +-- .moon/tasks/scad.yml
    |      one link to shared SCAD capability policy
    |
    `-- tools/tool.scad-project
           SCAD CLI + reusable workflows + capability policy
                  |
                  `-- docker.scad-toolchain image family
```

Release history: [`CHANGELOG.md`](CHANGELOG.md).

## Configuration

A current-generation consumer uses generic `project.yml` plus `project.scad.yml`.

`project.yml`:

```yaml
schema_version: 1

project:
  name: example.scad-project

profiles:
  - type: scad
    config: project.scad.yml

dependencies:
  - name: tool.scad-project
    role: tooling
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v0.14.x
```

The dependency ref is the human-readable immutable release contract. The git submodule
records the exact commit resolved for that release; consumer reusable-workflow callers use
the same semantic release ref instead of duplicating the opaque commit SHA.

`project.scad.yml` contains SCAD-domain intent, for example:

```yaml
paths:
  design_root: dsg/openscad
  build_root: bld
  render_root: dsg/openscad/render
  export_root: dsg/openscad/export

build_engine:
  engine: scons

openscad:
  common_flags:
    - --enable=object-function
  render_flags:
    - --render
  image_size: [1600, 1000]
  design_image_size: [640, 480]

design:
  include_externals: false
```

Dependency URL/path/ref/type come from generic `project.yml`. SCAD-specific external
metadata is matched by dependency name from the SCAD profile. The loader composes both
files into one internal project context.

The older combined `project.yml` remains a compatibility input. New consumers use the
split model.

See [`examples/project.yml`](examples/project.yml) and
[`examples/project.scad.yml`](examples/project.scad.yml).

## Visible capabilities

Migration 005 reduces the normal Moon model to real maintainer-visible capabilities:

```text
scad.docs    design documentation
scad.build   presentation renders/exports
scad.verify  verification
```

Standard commands, common stable inputs, output boundaries and Moon cache policy are
owned here in [`moon/tasks/scad.yml`](moon/tasks/scad.yml). A consumer links that file
once using Moon inheritance and selects only the capabilities it actually exposes.
Project-specific `moon.yml` content is limited to source-impact additions and exceptional
output overrides.

The SCAD CI planner validates that the Moon capability selection agrees with
`project.scad.yml`; a consumer cannot silently claim a Build/Verification capability that
its project configuration does not support, or omit one that is configured.

## Bootstrap and dependency update

The bootstrap engine is `tools/tool.git-project`, pinned by the parent repository gitlink.
Root `bootstrap.ps1` / `bootstrap.sh` launchers restore that exact bootstrap tool and then
establish managed dependencies declared in `project.yml`.

A SCAD consumer can use the small wrappers in [`consumer/`](consumer/) for an intentional
dependency update:

```powershell
.\update-repo.ps1
```

```bash
bash ./update-repo.sh
```

Those wrappers call:

```text
scad-project repo-update
    -> tool.git-project update
    -> scad-project workflow-sync
```

The generic tool moves dependency gitlinks. `workflow-sync` is SCAD-specific and aligns
consumer reusable-workflow calls with the configured `tool.scad-project` release ref from
`project.yml`. The gitlink remains the exact resolved commit; the workflow caller stays
human-readable as the same released version.

## Core commands

```text
scad-project config-lint
scad-project tooling-check
scad-project externals-check
scad-project externals-status
scad-project docs-lint
scad-project design-lint
scad-project design-build
scad-project build
scad-project verify
scad-project produce-build
scad-project produce-verification
scad-project build-audit
scad-project build-index
```

`config-lint` validates generic `project.yml` through the pinned `tool.git-project` when
the split configuration model is active and validates SCAD-specific configuration here.

`build` owns normal render/export output. `verify` owns the independent verification
domain: verification-only targets and project-specific checks. It does not materialize
normal Build output as a side effect.

`produce-build` and `produce-verification` remain stable composite producer actions for
explicit callers. Normal Migration-005 repository production uses the three coarse Moon
capabilities directly so each can be affected/cached independently.

`build-audit` consumes existing build-decision evidence plus explicit changed paths and
checks target-level rebuild correctness. See
[`docs/build-decision-audit.md`](docs/build-decision-audit.md).

## Directory-based builds

OpenSCAD build entrypoints can be discovered from configured directories:

```yaml
paths:
  render_root: dsg/openscad/render
  export_root: dsg/openscad/export
```

Conceptually:

```text
render_root/*.scad -> bld/png/*.png
export_root/*.scad -> bld/stl/*.stl
```

Optional `render.yml` and `export.yml` files beside entrypoints define variants, image
sizes and output-name patterns. Explicit `builds:` mappings remain available for
exceptional source/output mappings.

## Selective SCons build engine

SCons is an optional fine-grained backend behind the normal SCAD commands:

```yaml
build_engine:
  engine: scons
```

Moon decides/reuses whole capabilities. SCons, when configured, decides/reuses individual
CAD targets inside a capability.

The normal SCons cache is transported by normal CI only for SCons projects with
Build/docs capabilities. The separate Verification-SCons cache is transported only when
the project actually declares verification render/export targets. Direct projects do not
pay SCons cache restore/save cost simply because SCons is present in the runtime image.

SCons decisions use the outcomes `BUILT`, `CACHE_RESTORED`, `CURRENT` and `ERROR`.
See [`docs/build-decision-telemetry.md`](docs/build-decision-telemetry.md).

## Design documentation

Source `design.md` is authoritative; generated documentation goes under:

```text
bld/design/project/...
bld/design/ext/<external-name>/...
```

Canonical render declarations use `scad-render-defaults` and `scad-render`. Supported
engines are OpenSCAD and PythonSCAD. Explicit engine selection wins over suffix
inference.

`design.include_externals: false` suppresses generated external design docs while keeping
external CAD source available to builds.

## Source documentation

Structured `.scad` documentation follows upstream `openscad_docsgen` syntax. A structured
source begins with `File:` or `LibFile:` before Module/Function/etc.

```text
scad-project docs-lint
```

runs the upstream documentation check on project source.

## OpenSCAD warning policy

A zero process exit code is not sufficient proof of valid geometry. Shared command
execution rejects warning/error classes that indicate undefined values or broken geometry
while allowing known benign presentation warnings.

## Render post-processing

Configured PNGs may receive a watermark:

```yaml
rendering:
  watermark:
    text: "© 2026 brainboxemb"
```

The image operation is supplied by `docker.scad-toolchain` as
`scad-image-watermark`; this repository owns when it is invoked. STL output is never
watermarked.

## Verification

Verification-only OpenSCAD evidence can be declared separately from production output:

```yaml
verification:
  render_root: vrf/openscad/render
  export_root: vrf/openscad/export
  output_root: vrf/out
  commands:
    - [bash, scripts/run-project-checks.sh]
```

`scad-project verify` builds declared verification targets and then runs project-specific
commands. Declared geometry targets use the dedicated Verification-SCons state/cache only
when the project uses the SCons engine. Command-only verification does not need that
cache.

## Publication

Human-facing lifecycle names remain **Build** and **Verification**. Stable technical
workspace and publication identifiers use the compact portfolio convention `bld` and
`vrf`; see [`docs/publication-namespaces.md`](docs/publication-namespaces.md).

Recommended policy keeps generated content off the source branch:

```yaml
publication:
  production:
    source_branch: main
    build_branch: prod/bld
    verification_branch: prod/vrf
  development:
    pr_branch_prefix: dev/pr
  release:
    branch_prefix: rel
    tag_pattern: "v*"
    changelog: CHANGELOG.md
```

Default persistent publication therefore uses:

```text
dev/pr-N/bld
dev/pr-N/vrf
prod/bld
prod/vrf
rel/vX.Y.Z/bld
rel/vX.Y.Z/vrf
```

Normal production publishes mutable `prod/*` snapshots. Pull requests may publish
isolated `dev/pr-N/*` previews. Coordinated releases create immutable snapshots/assets
from one exact source commit. Explicit custom branch overrides remain supported for
compatibility; historical branches using older suffixes remain historical evidence.

Every generated snapshot includes `publication-info.txt` with current source, tooling and
runtime context. Source-derived Moon capability output does not use PR/ref/run/publication
values as cache identity.

## Normal reusable production workflow

`project-production.yml` implements the Migration-005 normal lifecycle:

1. resolve exact source/base;
2. ask released `tool.git-project v0.2.8` once for Moon's complete affected-task set;
3. stop before Python planner/image/SCons work when no SCAD capability is affected;
4. validate project intent and select the appropriate `docker.scad-toolchain v0.5.1`
   runtime profile;
5. restore only applicable Moon/SCons cache paths;
6. execute or hydrate required coarse capabilities in one Docker process;
7. add current-run finishing information on the host;
8. retain compact orchestration evidence;
9. publish changed Build/Verification families, overlapping both publishers on the same
   runner when both are needed.

Normal CI does **not** upload duplicate complete Build/Verification Actions artifacts by
default. Release is different: separate Build/Verify/finalize jobs require those complete
artifacts as an actual cross-job hand-off.

A thin consumer caller is typically:

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

See [`docs/production-workflow.md`](docs/production-workflow.md) for the detailed lifecycle,
including publication-safe Moon hydration when multiple capabilities contribute to one
complete Build tree.

## Release workflow

The coordinated Release workflow keeps its separate preflight, Build, Verify and finalize
jobs. Preflight uses the same SCAD project planner as normal production to select the
runtime image and applicable SCons cache paths, while complete Build/Verification
artifacts remain mandatory cross-job hand-off.

Release-request parsing, validation and request-branch cleanup are owned by the reusable
workflow. A consumer release caller therefore remains small:

```yaml
jobs:
  release:
    permissions:
      actions: read
      contents: write
      packages: read
    uses: brainboxemb/tool.scad-project/.github/workflows/project-release.yml@v0.14.x
```

The reusable Build and Verify workflows remain available for explicit domain execution
and for Release.

## Runtime image family

Current SCAD consumers use the released and externally qualified v0.5.1 image
family. This runtime adds the pinned `openscad-new-dimensions` library to the
shared OpenSCAD capability set while preserving the existing OpenSCAD/full
profile split:

```text
OpenSCAD-focused:
  ghcr.io/brainboxemb/scad-toolchain-openscad:v0.5.1

Full/dual OpenSCAD + PythonSCAD:
  ghcr.io/brainboxemb/scad-toolchain:v0.5.1
```

The effective runtime is derived from SCAD project configuration rather than repository
name. `scad-toolchain-info` reports exact runtime/tool versions.

## Direct dependency rule

Normal repositories initialize only their direct dependencies. Nested submodules that
belong to a consumed library's standalone development environment are not recursively
initialized by a parent consumer unless a dedicated integration requires them.

## Development workflow

Normal changes use issue -> numbered feature branch -> draft PR -> evidence -> review ->
merge. See [`AGENTS.md`](AGENTS.md) for the repository rules.

Cross-project architecture and rollout order are coordinated from
[`brainboxemb.meta`](https://github.com/brainboxemb/brainboxemb.meta).

The model, code and documentation are being developed with the assistance of ChatGPT.
