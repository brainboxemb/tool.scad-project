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

Documentation: [`docs/README.md`](docs/README.md) · Release history: [`CHANGELOG.md`](CHANGELOG.md).

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
  render_roots:
    - dsg/openscad/render3d
    - dsg/openscad/render2d
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

Root `update.ps1` / `update.sh` launchers are generic managed files from
`tool.git-project`. A normal update is therefore:

```text
root update.*
    -> tool.git-project update
        -> generic dependency movement
        -> optional role:tooling post-update hooks
            -> tool.scad-project/consumer/post-update.*
```

The SCAD post-update hook is Python-free and owns only reusable-workflow ref
synchronization. It aligns consumer workflow calls with the configured
`tool.scad-project` release ref from `project.yml`.

`tool.scad-project` does not ship a second root updater implementation or
compatibility wrapper. Current consumers use the generic managed root launcher.

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
[`docs/20-10-build-decision-audit.md`](docs/20-10-build-decision-audit.md).

## Build and render model

The normal SCAD project flow has three user-facing output families. They share
the same project configuration and build/cache machinery, but they have
different purposes:

| Source/control | Purpose | Normal output |
| --- | --- | --- |
| render roots + `render.yml` | presentation renders and simple 2D vector exports | `bld/png/*.png` or `bld/svg/*.svg` |
| export root + `export.yml` | printable/manufacturing geometry | `bld/stl/*.stl` |
| project `drawing` producer | composed technical drawing sheets | canonical `bld/drawing/*.svg` plus optional PNG/PDF |
| component `design/design.md` | generated design documentation with embedded renders | `bld/design/.../design.md` + `img/*.png` or `img/*.svg` |

PNG is the default render format. SVG is an opt-in 2D OpenSCAD output format.
STL remains the export format.

`builds:` entries are an escape hatch for exceptional source/output mappings;
they are not the normal way to organise project renders.

## Directory-based renders and exports

A project may use one legacy render directory:

```yaml
paths:
  render_root: dsg/openscad/render
  export_root: dsg/openscad/export
```

or multiple render roots when 3D presentation renders and 2D drawing sources
should be kept separate:

```yaml
paths:
  render_roots:
    - dsg/openscad/render3d
    - dsg/openscad/render2d
  export_root: dsg/openscad/export
```

Every `.scad` entrypoint directly inside a configured render root becomes a
render target. Every `.scad` entrypoint directly inside `export_root` becomes
an STL target.

A render directory can contain a `render.yml`. Without one, or without an
explicit `format`, the render format is PNG:

```yaml
defaults:
  format: png
  image_size: [1600, 1000]
```

That produces:

```text
dsg/openscad/render3d/assembly.scad
    -> bld/png/assembly.png
```

A 2D drawing directory can select SVG once for all entrypoints in that
directory:

```yaml
# dsg/openscad/render2d/render.yml
defaults:
  format: svg
```

That produces:

```text
dsg/openscad/render2d/receiver-profile.scad
    -> bld/svg/receiver-profile.svg
```

Profiles in `render.yml` may override defaults for selected files. For
example, one file can switch to SVG while the rest remain PNG:

```yaml
defaults:
  format: png
  image_size: [1600, 1000]

profiles:
  vector-drawing:
    format: svg
    files:
      - receiver-profile.scad
```

The output-format contract is:

```text
render format png -> bld/png/*.png
render format svg -> bld/svg/*.svg
export_root        -> bld/stl/*.stl
```

PNG is a raster presentation render. It uses the configured render flags,
camera/autofit behaviour, image size and optional watermarking.

SVG is a true 2D OpenSCAD export. The SCAD entrypoint must therefore produce
2D geometry. Raster-only camera, image-size and watermark settings are not
applied to SVG.

Explicit `builds:` mappings may also target `.png`, `.stl` or `.svg`
when a project has an exceptional source/output mapping:

```yaml
builds:
  - name: receiver-drawing
    source: dsg/openscad/drawing/receiver.scad
    output: bld/svg/receiver.svg
```

## Project-owned technical drawings

A composed engineering drawing is different from a raw OpenSCAD SVG export.
Projects that need sheet layout, dimensions, labels, title blocks and optional
PNG/PDF publication can declare one project-owned drawing producer:

```yaml
drawing:
  command:
    - python3
    - dsg/drawing/build.py
  inputs:
    - dsg/drawing/build.py
    - dsg/openscad/specification/mating_profiles.scad
  outputs:
    - bld/drawing/mating-profiles.svg
    - bld/drawing/mating-profiles.png
    - bld/drawing/mating-profiles.pdf
```

The first output is the canonical SVG and is mandatory. Additional declared
outputs may be SVG, PNG or PDF. All drawing outputs must stay below
`paths.build_root`.

The command is executed once from the project root and owns the actual drawing
implementation. A normal consumer can therefore keep a readable code-driven
pipeline such as:

```text
OpenSCAD geometry/projections
    -> project Python + drawsvg
    -> canonical SVG
    -> Python invokes Inkscape
    -> optional PNG / PDF
```

`tool.scad-project` does not contain a drawing template and does not duplicate
drawsvg/Inkscape behavior. It validates the producer contract, selects the
dedicated drawing runtime and checks that every declared output was produced.

With the direct build engine the producer runs once per build. With SCons,
`drawing.inputs`, the command and all declared outputs participate in target
identity; declared `.scad` inputs also receive normal transitive OpenSCAD
dependency scanning. Python helper modules or other producer inputs should be
listed explicitly.

The current runtime family does not combine PythonSCAD and the drawing profile,
so configuring both `pythonscad:` and `drawing:` is rejected explicitly.

## Design documentation

A project may define a shared specification for an interface/product contract,
then keep component implementation design documents next to their geometry:

```text
dsg/openscad/
  specification/
    specification.md
  components/
    example/
      example.scad
      design/
        design.md
```

`specification/specification.md` and `design/design.md` use the same render
declarations. Generated documentation lists project specifications first, then
component design documents. This keeps **what the interface must be** separate
from **how each component realizes it**.

The source Markdown files are authoritative. `scad-project design-build`
copies the document into the generated design tree, renders its declared
figures and replaces each render declaration with a normal Markdown image
reference:

```text
bld/design/project/...
bld/design/ext/<external-name>/...
```

### Normal PNG example

PNG is the default here as well. A typical OpenSCAD design document first
declares defaults for its component:

```md
<!-- scad-render-defaults
engine: openscad
source: example.scad
module: example_design
size: [1200, 800]
-->
```

A render block then selects one view:

```md
## Final shape

<!-- scad-render
view: final
vpr: [70, 0, 30]
-->
```

If no `image:` is supplied, the generated filename is derived from declaration
order and view name, for example:

```text
img/01-final.png
```

For PNG renders, `size`, `vpr`, `vpt` and `vpd` are available. `vpr`
alone uses autofit; an exact camera may provide `vpr`, `vpt` and `vpd`
together. A render block may override document defaults.

### SVG variant for a 2D drawing

The same `scad-render` declaration can instead request vector output. The
drawing source must produce true 2D OpenSCAD geometry:

```md
## Dimensioned front profile

<!-- scad-render
engine: openscad
source: example_drawing.scad
module: example_front_drawing
format: svg
image: 02-dimensioned-front-profile.svg
-->
```

The generated document then links to:

```text
img/02-dimensioned-front-profile.svg
```

SVG does not use `size`, `vpr`, `vpt` or `vpd`; those fields are rejected
for SVG instead of being silently ignored. SVG currently requires the OpenSCAD
engine.

This means PNG and SVG are not two separate documentation systems:

```text
design.md
  scad-render (default format: png) -> img/*.png
  scad-render (format: svg)         -> img/*.svg
```

`design.include_externals: false` suppresses generated external specification/design docs
while keeping external CAD source available to builds.

## Selective SCons build engine

SCons is an optional fine-grained backend behind the same normal SCAD commands:

```yaml
build_engine:
  engine: scons
```

Moon decides/reuses whole capabilities. SCons, when configured, decides/reuses
individual CAD targets inside a capability.

The selected output format is part of target/cache identity. PNG and SVG have
different output targets and different target specifications; changing a render
from PNG to SVG cannot restore a cached PNG as if it were current SVG output.
The same applies to figures generated from `design.md`.

The normal SCons cache is transported by normal CI only for SCons projects with
Build/docs capabilities. The separate Verification-SCons cache is transported
only when the project actually declares verification render/export targets.
Direct projects do not pay SCons cache restore/save cost simply because SCons
is present in the runtime image.

SCons decisions use the outcomes `BUILT`, `CACHE_RESTORED`, `CURRENT` and
`ERROR`. See
[`docs/30-12-build-decision-telemetry.md`](docs/30-12-build-decision-telemetry.md).

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
`vrf`; see [`docs/30-10-publication-namespaces.md`](docs/30-10-publication-namespaces.md).

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

## Normal reusable CI workflow

`reusable-ci.yml` implements the normal PR/main integration lifecycle:

1. resolve exact source/base;
2. ask released `tool.git-project v0.2.13` once for Moon's complete affected-task set;
3. stop before Python planner/image/SCons work when no SCAD capability is affected;
4. validate project intent and select the appropriate `docker.scad-toolchain v0.6.1`
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
    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-ci.yml@v0.15.11
    with:
      cache_namespace: my-repository-scad-production-v2
```

See [`docs/40-11-ci-workflow.md`](docs/40-11-ci-workflow.md) for the detailed lifecycle,
including publication-safe Moon hydration when multiple capabilities contribute to one
complete Build tree.

## Release workflow

The coordinated Release workflow keeps its separate preflight, Build, Verify and finalize
jobs. Preflight uses the same SCAD project planner as normal CI to select the
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
    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-release.yml@v0.15.11
```

The reusable Build and Verify workflows remain available for explicit domain execution
and for Release.

## Runtime image family

Current SCAD consumers use the released and externally qualified v0.6.1 image
family. Runtime selection follows configured capabilities:

```text
OpenSCAD-focused:
  ghcr.io/brainboxemb/scad-toolchain-openscad:v0.6.1

Technical drawing:
  ghcr.io/brainboxemb/scad-toolchain-drawing:v0.6.1
  adds drawsvg 2.4.2 and Inkscape

Full/dual OpenSCAD + PythonSCAD:
  ghcr.io/brainboxemb/scad-toolchain:v0.6.1
```

The current runtime line no longer carries `openscad-new-dimensions`; composed
technical-drawing annotations belong to the project-owned Python/SVG layer.
The immutable external qualification record is
`docker.scad-toolchain.test@test-v0.6.1-toolchain-v0.6.1`.

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
