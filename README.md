# tool.scad-project

Reusable workflow tooling for configuration-driven SCAD projects using OpenSCAD and PythonSCAD.

Repository role:

```text
docker.scad-toolchain
    runtime and external capabilities

tool.scad-project
    reusable project workflow and conventions

template.scad-project
    reference consumer
```

Release history: [`CHANGELOG.md`](CHANGELOG.md)

The CLI is:

```text
scad-project
```

Initial commands:

```text
scad-project config-lint
scad-project externals-check
scad-project externals-status
scad-project externals-init
scad-project externals-sync
scad-project externals-deinit
scad-project docs-lint
scad-project design-lint
scad-project design-build
scad-project build
scad-project verify
```

## Configuration

A consuming project has a root `project.yml`.

```yaml
project:
  name: example.scad-project

paths:
  design_root: dsg
  build_root: bld

design:
  include_externals: false

build_engine:
  engine: scons

openscad:
  common_flags:
    - --enable=object-function
  render_flags:
    - --render
  image_size: [1600, 1000]

rendering:
  watermark:
    text: "© 2026 brainboxemb"

externals:
  - name: lib.scad.clamps
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.clamps.git
    path: dsg/openscad/ext/lib.scad.clamps
    required_file: openscad/tube-clamp/tube_clamp.scad

builds:
  - name: assembly-png
    source: dsg/openscad/render/assembly.scad
    output: bld/png/assembly.png

  - name: assembly-stl
    source: dsg/openscad/render/assembly.scad
    output: bld/stl/assembly.stl
```

`build_engine` is optional. Omitting it keeps the backwards-compatible direct
build engine. `design.include_externals` defaults to `true`; set it to `false`
when a consumer should publish only its project-owned design documentation.

## Directory-based builds

Normal OpenSCAD build entrypoints can be discovered from configured directories
instead of being listed one by one under `builds:`.

```yaml
paths:
  design_root: dsg
  build_root: bld
  render_root: dsg/openscad/render
  export_root: dsg/openscad/export
```

Rules:

```text
render_root/*.scad -> build_root/png/*.png
export_root/*.scad -> build_root/stl/*.stl
```

Only direct `.scad` children are discovered. Subdirectories are not scanned.
Underscores in entrypoint filenames are converted to hyphens in generated
output names.

Optional `render.yml` and `export.yml` files beside the entrypoints describe
special build behavior. Files not assigned to a profile are built once with
normal defaults.

Example `render.yml`:

```yaml
defaults:
  image_size: [2560, 1440]

profiles:
  multi-size:
    sizes: [small, medium, large]
    image_size: [1800, 1200]
    files:
      - middle_coupler.scad
```

This generates:

```text
middle-coupler-small.png
middle-coupler-medium.png
middle-coupler-large.png
```

and invokes OpenSCAD with `-D size="<value>"` for each configured size.

A profile-level `image_size` overrides `defaults.image_size`, which in turn
overrides `openscad.image_size` for those directory-based render entrypoints.

The same `sizes` and `files` profile structure is supported by `export.yml`
for STL generation. `image_size` has no effect on STL output.

The existing root `builds:` list remains supported for compatibility and for
exceptional explicit source/output mappings. If an explicit build and a
directory-discovered build resolve to the same output path, the explicit build
wins.

## Selective SCons build engine

`tool.scad-project` v0.8.0 adds an optional SCons backend behind the existing
`scad-project build` command:

```yaml
build_engine:
  engine: scons
```

The direct engine remains the default when this section is omitted. Both
engines consume the same configured target model; enabling SCons does not add a
second `render.yml`, `export.yml` or `builds:` format.

The SCons backend tracks OpenSCAD dependencies through transitive `use` and
`include` references. Literal file inputs loaded through `import()` or
`surface()` are tracked as leaf dependencies. A dynamic file-loading expression
that cannot be represented deterministically is rejected in SCons mode instead
of risking a stale cached output; use a literal file path or the direct engine
for such a target.

Reusable Build and Verify workflows persist SCons `CacheDir` data through
GitHub Actions cache. A clean runner does not need the previous `bld/` tree or
`.sconsign`: unchanged missing outputs can be restored by build signature while
only targets affected by changed dependencies are executed again. Cache
namespaces include the repository, immutable toolchain version, exact
`tool.scad-project` gitlink and relevant project inputs.

The reusable Build workflow also caches the complete generated `bld/design`
tree. An exact design-input cache hit restores that tree and skips
`design-build`. A changed design input currently rebuilds the whole generated
design tree; per-document design dependency selection is intentionally deferred.

When SCons is active, Build uploads a small `last-build.json` report artifact
showing which configured targets were executed and which were restored/current.

## Render post-processing

PNG build outputs can optionally receive a watermark through project
configuration:

```yaml
rendering:
  watermark:
    text: "© 2026 brainboxemb"
```

When configured, `scad-project build` first renders the normal PNG and then
calls the public `scad-image-watermark` command supplied by
`docker.scad-toolchain`.

The responsibility split is intentional:

```text
docker.scad-toolchain
    -> generic image operation

tool.scad-project
    -> configuration and orchestration

consumer project
    -> watermark text/policy
```

The setting applies only to configured PNG build outputs. STL builds and
generated design-documentation images are unchanged.

## Design documentation

Preferred structure:

```text
component/
├── component.scad
└── design/
    ├── design.md
    └── img/
```

### Source view — preferred

```markdown
<!-- scad-design
type: source-view
module: tube_design
view: bore
image: 02-bore.png
-->
```

This reuses an existing OpenSCAD module/view and avoids duplicating geometry in
Markdown.

### Inline illustration

Small documentation-only illustrations are also supported:

````markdown
<!-- scad-design
type: inline
image: wall-thickness.png
-->

```openscad
difference() {
    circle(d=20);
    circle(d=16);
}
```
````

Inline OpenSCAD is for explanation, not for duplicating reusable project
geometry.

Presentation metadata such as `vpr`, `vpt`, `vpd` and `size` can live in the
render declaration.


## Design render engines

`design-build` supports two render engines:

```text
openscad
pythonscad
```

The engine can be explicit:

```markdown
<!-- scad-render-defaults
engine: pythonscad
source: render.py
-->
```

or inferred from the source entrypoint:

```text
.scad -> openscad
.py   -> pythonscad
```

An explicit `engine` always takes precedence over suffix inference. Source file
type and render engine are deliberately separate concepts; this leaves room for
PythonSCAD entrypoints that consume `.scad` libraries through `osuse()` or
`osinclude()`.

OpenSCAD source views use:

```text
source + module + view
```

PythonSCAD source views use:

```text
source + view
```

For PythonSCAD the tool invokes the entrypoint with:

```text
-D design_view="<view>"
```

so render scripts can read:

```python
design_view = globals().get("design_view", "final")
```

PythonSCAD project defaults may be configured separately:

```yaml
pythonscad:
  common_flags:
    - --trust-python
  render_flags:
    - --render
```

Inline Markdown geometry remains OpenSCAD-only for now.

## Source documentation

Structured comments in `.scad` files should follow `openscad_docsgen` syntax.

A documented file starts with:

```scad
// File: component.scad
```

or:

```scad
// LibFile: component.scad
```

before `Module`, `Function`, `Constant`, etc.

`scad-project docs-lint` runs the upstream docsgen test mode on documented
project source.

## Render policy

`design-render` renders the complete expected image set first. Stale
`design/img/*.png` files are only removed after all expected renders succeed.

## Runtime

Current expected runtime:

```text
ghcr.io/brainboxemb/scad-toolchain:v0.4.1
```

This runtime contains SCons 4.11.1 for the selective build backend. The project
tool intentionally remains separate from the Docker image.

The model, code and documentation are being developed with the assistance of ChatGPT.

## Bootstrap and offline-friendly local use

`tool.scad-project` is intended to be pinned in a consuming repository as a Git
submodule:

```text
tools/tool.scad-project
```

The bootstrap scripts live in this repository:

```text
bootstrap/bootstrap.ps1
bootstrap/bootstrap.sh
```

When starting a new project, copy the appropriate bootstrap file to the root of
the consuming repository.

On Windows:

```powershell
.\bootstrap.ps1
```

The bootstrap script deliberately contains only enough logic to:

1. register `tool.scad-project` as `tools/tool.scad-project` when necessary;
2. initialize that submodule;
3. invoke the local tool to initialize the project's configured externals.

After the repository and its submodules have been populated once, normal local
use does not require fetching `tool.scad-project` from GitHub again. The parent
repository's gitlink pins the exact tool commit.

Run the local tool directly:

```powershell
.\tools\tool.scad-project\scad-project.ps1 design-lint
.\tools\tool.scad-project\scad-project.ps1 design-render
.\tools\tool.scad-project\scad-project.ps1 build
```

The launcher executes the Python package directly from the checked-out tool
source; a pip install of `tool.scad-project` itself is not required.

## External management

Project externals are declared in `project.yml`:

```yaml
externals:
  - name: lib.scad.clamps
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.clamps.git
    path: dsg/openscad/ext/lib.scad.clamps
    required_file: openscad/tube-clamp/tube_clamp.scad
```

Commands:

```text
scad-project externals-status
    show registered/initialized state and current commit

scad-project externals-init
    register missing configured submodules and initialize all externals

scad-project externals-sync
    sync .gitmodules and restore the exact commits pinned by parent gitlinks

scad-project externals-deinit
    remove local submodule working trees while preserving .gitmodules/gitlinks

scad-project externals-check
    verify required externals and required files are available
```

`externals-deinit` is intentionally non-destructive at repository level. It
does not `git rm` the submodule. A future explicit remove command should handle
that separately.

The old `libraries:` config key and `libraries-check` CLI command remain
accepted temporarily for v0.1 migration, but new projects should use
`externals:`.

### Shell-script portability

When invoking the shell launcher from CI or a bootstrap script, prefer:

```bash
bash ./scad-project.sh <command>
```

rather than relying on `./scad-project.sh`. This keeps projects created from a
ZIP or managed on Windows from depending on preservation of the Unix executable
bit.

## Python-free bootstrap

Bootstrap is deliberately independent of Python and of the `scad-project` CLI.

Required local tools:

```text
PowerShell + Git        (Windows)
bash + Git              (Linux/macOS)
```

The consumer repository ships a `.gitmodules` file containing the technical
submodule registrations. The bootstrap script:

1. reads every path/URL from `.gitmodules`;
2. detects whether the corresponding gitlink already exists in the parent repo;
3. repairs/registers missing gitlinks with `git submodule add --force`;
4. preserves already-correct submodules;
5. runs `git submodule sync --recursive`;
6. runs `git submodule update --init --recursive`.

This makes the script safe to re-run after a partially completed bootstrap.

`project.yml` remains the semantic project configuration. `.gitmodules` is the
technical Git representation required before Python/project tooling is
available. `scad-project` can later lint that these declarations agree.

A bootstrap must never require Python merely to obtain the project's pinned
tooling and CAD-library submodules.

## OpenSCAD warning validation

OpenSCAD can return exit code `0` while still reporting warnings that indicate
invalid or skipped geometry. `scad-project` therefore inspects OpenSCAD output
after successful commands.

The following warning classes are treated as errors:

```text
Ignoring unknown variable
undefined operation
Unable to convert ... parameter
warnings involving undef/undefined values
```

Known presentation-only warnings are allowed, including:

```text
Viewall and autocenter disabled in favor of $vp*
```

This prevents `design-render` or `build` from reporting success merely because
OpenSCAD returned a zero exit code while geometry was actually incomplete.

## Generated design documentation

Source `design.md` files stay on the normal code branch. Generated images do
not live beside them.

Use one optional defaults block near the top of a design document:

```markdown
<!-- scad-render-defaults
module: tube_design
vpr: [70, 0, 35]
-->
```

Normal design steps can then stay compact:

```markdown
<!-- scad-render
view: outer
-->

<!-- scad-render
view: bore
-->

<!-- scad-render
view: final
-->
```

Images are numbered automatically from their order in the file:

```text
01-outer.png
02-bore.png
03-final.png
```

`image:` remains available when a fixed custom filename is useful. Any value
inside an individual `scad-render` overrides the document defaults.

Image-size precedence is:

```text
scad-render size
    ↓
scad-render-defaults size
    ↓
project.yml openscad.design_image_size
```

The recommended project default is:

```yaml
openscad:
  design_image_size: [640, 480]
```

Normal project renders can keep a larger `openscad.image_size`.

Run:

```text
scad-project design-build
```

The tool discovers project and configured-external design documents, renders
their declared views, and generates:

```text
bld/design/
├── README.md
├── project/
│   └── .../design/
│       ├── design.md
│       └── img/
└── ext/
    └── <external-name>/
        └── .../design/
            ├── design.md
            └── img/
```

The generated `design.md` replaces render declarations with ordinary Markdown
image links. The source Markdown and external checkouts are never modified.

Set:

```yaml
design:
  include_externals: false
```

to omit external-library design documentation from a consumer build while
keeping those external CAD sources available to project models. The default is
`true` for backwards compatibility.

`scad-design` remains accepted as a compatibility syntax while older libraries
are migrated, but new documentation should use `scad-render`.

## Publication and release policy

Generated content belongs off the source branch. Normal builds resolve their
publication target from the GitHub ref that produced the build, while a
coordinated release generates immutable versioned snapshots and downloadable
release assets from one exact source commit.

Recommended configuration:

```yaml
publication:
  production:
    source_branch: main
    build_branch: prod/build
    verification_branch: prod/verification

  development:
    build_branch: dev/build
    verification_branch: dev/verification

  tags:
    pattern: "v*"

  release:
    branch_prefix: rel
    tag_pattern: "v*"
    changelog: CHANGELOG.md
```

The standard behavior is:

| Source context | Build | Verification |
| --- | --- | --- |
| production branch (`main`) | mutable `prod/build` | mutable `prod/verification` |
| other branch | mutable `dev/build` | mutable `dev/verification` |
| pull request | workflow artifact only | workflow artifact only |
| ordinary matching tag build | workflow artifact only | workflow artifact only |
| coordinated release `vX.Y.Z` | immutable `rel/vX.Y.Z/build` | immutable `rel/vX.Y.Z/verification` |

Development and production branches are mutable snapshots. Every generated
artifact and branch snapshot receives a root `publication-info.txt` containing
the source repository, ref type, ref, commit, actor, workflow-run URL, tool and
runtime provenance.

A coordinated release is stricter. Its requested source SHA must equal the
current HEAD of the configured production source branch at preflight time. That
same HEAD is fetched and checked again immediately before immutable
finalization. This prevents releasing a stale production ancestor and closes a
race where the production branch advances while release Build/Verify jobs are
running.

Build and Verify run first with branch publication disabled. Only after both
succeed does finalization:

1. download those exact workflow artifacts;
2. build deterministic release ZIPs and `SHA256SUMS.txt`;
3. verify the generated checksums;
4. generate release notes from the configured changelog;
5. create immutable `rel/vX.Y.Z/build` and `rel/vX.Y.Z/verification` branches;
6. create the annotated source tag;
7. create the GitHub Release and upload the ZIP/checksum assets.

If finalization fails after immutable branches were created, the workflow rolls
back the incomplete release refs rather than leaving a partial release.
Existing `rel/*` branches are never force-pushed.

The older flat configuration remains accepted during migration:

```yaml
publication:
  build_branch: build
  verification_branch: verification
```

but new projects should use the explicit production/development/release model.

CI prepares provenance before artifact upload:

```text
scad-project publication-info-build
scad-project publication-info-verification
```

and resolves normal snapshot destinations when publishing:

```text
scad-project publish-build
scad-project publish-verification
```

### Camera and image handling

A declaration may use `size: [width, height]`. A declaration containing only
`vpr` uses that orientation together with OpenSCAD auto-centering/view-all.
Use `vpr`, `vpt` and `vpd` together only when an exact camera is required.

Generation also copies static files that already live next to a source
`design.md`. This keeps older external libraries readable while they migrate to
`scad-design` declarations. Missing legacy images in an external produce a
warning; missing project-owned images fail the build.

## Direct dependency checkout

Submodule traversal is intentionally **non-recursive by default**.

A consumer initializes only the dependencies that it directly declares in its
own repository configuration:

```text
template.scad-project
├── tools/tool.scad-project
└── dsg/openscad/ext/lib.scad.clamps
```

When `lib.scad.clamps` is consumed by the template, its own development
submodule is not automatically initialized:

```text
dsg/openscad/ext/lib.scad.clamps/tools/tool.scad-project
    not checked out by the template
```

If `lib.scad.clamps` is cloned as a standalone repository, its own bootstrap
initializes its direct tooling dependency normally.

This rule applies to:

- `bootstrap.ps1` / `bootstrap.sh`;
- `update-repo.ps1` / `update-repo.sh`;
- `repo-sync` / `repo-update`;
- `externals-init` / `externals-sync`;
- reusable GitHub workflows.

Recursive checkout is reserved for an explicit integration test whose purpose
is to validate the entire dependency tree.

## Versioned repository dependencies

`project.yml` is the policy source for both project tooling and reusable CAD
libraries. The parent repository's Git submodule gitlinks remain the lock.

Example:

```yaml
tooling:
  tool_scad_project:
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v0.9.0

externals:
  - name: lib.scad.clamps
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.clamps.git
    path: dsg/openscad/ext/lib.scad.clamps
    ref: latest
    required_file: openscad/tube-clamp/tube_clamp.scad
```

`ref` is per dependency and supports:

```text
v0.9.0
    exact tag

latest
    newest stable vX.Y.Z tag

main
develop
feature-branch
    current head of that remote branch
```

`latest` is deliberately not another spelling for `main`.

The repository operations are:

```text
bootstrap
    establish the submodule registrations/checkouts

repo-sync
    restore the exact commits already locked by the parent gitlinks

repo-update
    resolve each configured ref, update the submodule gitlinks and align
    thin reusable-workflow callers

repo-status
    show configured refs and current commits
```

For convenience, consumer repositories can copy:

```text
update-repo.ps1
update-repo.sh
```

Then a normal intentional dependency update is simply:

```powershell
.\update-repo.ps1
```

`repo-update` never commits. It leaves `project.yml`, workflow callers and
changed gitlinks available for normal `git diff` / `git status` review.

For tooling, workflow callers are derived from the resolved tooling ref:

```text
ref: v0.9.0  -> @v0.9.0
ref: latest  -> @<resolved newest tag>
ref: main    -> @main
```

This keeps dependency policy in `project.yml` while satisfying GitHub Actions'
requirement that reusable workflow refs are literal in workflow YAML.

### Python-free repository updater

`update-repo.ps1` and `update-repo.sh` are deliberately part of the bootstrap
layer and do not invoke Python or the `scad-project` CLI.

They require only Git plus PowerShell/bash, parse only the dependency subset of
`project.yml`, resolve exact tags / `latest` / branch refs, update gitlinks and
align reusable workflow refs.

On Windows:

```powershell
.\update-repo.ps1
```

works before Python is installed.

## Workflow timeout policy

Reusable workflows use deliberately short fail-safe timeouts. Normal SCAD
project workloads are expected to finish in minutes, so a stuck render or
publish step should not occupy a runner for an hour.

```text
reusable Build job         15 min
reusable Verify job        15 min
setup/lint/upload/publish   2 min per step
design/build/verification   5 min per heavy step
tool Test job              15 min
tool Release job           10 min
```

These limits follow the same philosophy as the earlier reusable OpenSCAD
Actions workflows: enough headroom for normal rendering, but intentionally
short when a process hangs.

## Reusable GitHub workflows

Consumer repositories should keep their GitHub Actions files thin and pin the
reusable workflows to the same `tool.scad-project` release as their local tool
submodule.

Build workflow:

```yaml
jobs:
  build:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-build.yml@v0.9.0
```

Projects with separate functional verification can additionally use:

```yaml
jobs:
  verify:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-verify.yml@v0.9.0
    with:
      verification_path: vrf/out
```

Projects that use coordinated releases keep a similarly thin caller. The
caller must grant `actions: read` because the reusable release finalizer
downloads the Build and Verify artifacts from the same workflow run:

```yaml
permissions:
  actions: read
  contents: write
  packages: read

jobs:
  release:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-release.yml@v0.9.0
    with:
      version: ${{ inputs.version }}
      source_sha: ${{ inputs.source_sha }}
```

Inside `project-release.yml`, the nested Build and Verify calls use local
same-revision reusable-workflow references. Therefore a release invoked at
`@v0.9.0` cannot silently use Build/Verify logic from a later tool revision.

The reusable build workflow standardizes:

- toolchain selection;
- tooling-version validation;
- configuration/external/source/design linting;
- generated-design cache restore/build;
- dependency-selective configured PNG/STL builds when SCons is enabled;
- build artifact upload;
- configured generated build snapshot publication.

The reusable verification workflow runs the generic source/build verification,
then project-specific `verification.commands`, and can publish the configured
verification output to the configured verification snapshot branch.

### Tooling version alignment

A consumer declares the expected tool release in `project.yml`:

```yaml
tooling:
  tool_scad_project:
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v0.9.0
```

For a release-pinned consumer, these three references should represent the same
release:

```text
project.yml tooling.tool_scad_project.ref
Git submodule tools/tool.scad-project
reusable workflow @v0.9.0
```

`scad-project tooling-check` verifies the running CLI against `project.yml` and,
inside the reusable workflows, also checks the workflow release marker.

### Functional verification configuration

Projects that publish verification evidence can declare argv-style commands:

```yaml
verification:
  commands:
    - [bash, scripts/run-verification.sh]
    - [bash, scripts/build-verification-index.sh]
  output_root: vrf/out

publication:
  production:
    source_branch: main
    verification_branch: prod/verification
  development:
    verification_branch: dev/verification
  release:
    branch_prefix: rel
    tag_pattern: "v*"
```

Commands are stored as argument lists rather than shell strings so quoting and
execution remain explicit.

## Canonical bootstrap

The canonical consumer bootstrap scripts live in:

```text
bootstrap/bootstrap.ps1
bootstrap/bootstrap.sh
```

Consumer repositories copy these scripts to their repository root. The
bootstrap handles missing parent directories (for example `tools/`) and ends by
verifying that every declared submodule exists as a Git gitlink with mode
`160000`. It must fail instead of reporting success when registration is
incomplete.

## Generated provenance

Every generated build or verification snapshot contains:

```text
publication-info.txt
```

This is the current-generation replacement for the classic
`openscad-build.txt` file. It keeps source and runtime evidence together
instead of creating engine-specific metadata files.

The record contains:

```text
Source
    repository
    ref / commit
    workflow run

Tooling
    immutable SCAD toolchain image
    SCAD toolchain release
    tool.scad-project release

Runtime components
    scad-toolchain-info output
    OpenSCAD
    PythonSCAD
    SCons
    BOSL2 / pybosl2
    Shapely
    openscad_docsgen
    Pillow
```

The immutable Docker image is the primary runtime version pin. Exact component
versions remain useful diagnostic and reproduction evidence, but they are
managed as part of that image.

## Standard generated build index

`scad-project build-index` writes the common root `bld/README.md`. It links only
to generated sections that actually exist (`design`, `png`, `stl`) and records
the resolved publication context/branch. This keeps mutable `prod/*` snapshots
and immutable `rel/<version>/*` snapshots self-describing when browsed on
GitHub.
