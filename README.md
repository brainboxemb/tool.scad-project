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
ghcr.io/brainboxemb/scad-toolchain:v0.3.1
```

The project tool intentionally remains separate from the Docker image.

## Scope of v0.1.0

This first version establishes the reusable config/design/build layer.

Not yet included:

- verification branch publication;
- copyright/watermark processing;
- project scaffolding/generation;
- embedding this package into the Docker image.

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

`scad-design` remains accepted as a compatibility syntax while older libraries
are migrated, but new documentation should use `scad-render`.


## Publication policy

Generated content belongs off the source branch. Publication is resolved from
the GitHub ref that produced the build, so projects do not need a temporary
workflow or temporary `project.yml` edit for development branches.

Recommended configuration:

```yaml
publication:
  production:
    source_branch: main
    build_branch: build
    verification_branch: verification

  development:
    build_branch: dev/build
    verification_branch: dev/verification

  tags:
    pattern: "v*"
```

The standard behavior is:

| Source context | Build | Verification |
| --- | --- | --- |
| production branch (`main`) | mutable `build` branch | mutable `verification` branch |
| other branch | mutable `dev/build` branch | mutable `dev/verification` branch |
| pull request | workflow artifact only | workflow artifact only |
| matching version tag | workflow artifact only | workflow artifact only |

Development branches deliberately share one mutable pair of publication
branches. The newest development run replaces the previous snapshot. Every
generated artifact and branch snapshot therefore receives a root
`publication-info.txt` containing the source repository, ref type, ref, commit,
actor and workflow-run URL.

Tags never overwrite the mutable production or development branches. In v0.5.0
they produce immutable workflow-run artifacts only. Attaching those artifacts
to a GitHub Release can be added as a separate release policy without changing
the branch semantics.

The older flat configuration remains accepted during migration:

```yaml
publication:
  build_branch: build
  verification_branch: verification
```

CI prepares provenance before artifact upload:

```text
scad-project publication-info-build
scad-project publication-info-verification
```

and then resolves the destination when publishing:

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
    ref: v0.6.0

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
v0.6.0
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
ref: v0.6.0  -> @v0.6.0
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

## Reusable GitHub workflows

Consumer repositories should keep their GitHub Actions files thin and pin the
reusable workflows to the same `tool.scad-project` release as their local tool
submodule.

Build workflow:

```yaml
jobs:
  build:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-build.yml@v0.6.0
```

Projects with separate functional verification can additionally use:

```yaml
jobs:
  verify:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-verify.yml@v0.6.0
    with:
      verification_path: vrf/out
```

The reusable build workflow standardizes:

- toolchain selection;
- tooling-version validation;
- configuration/external/source/design linting;
- OpenSCAD and PythonSCAD generated design documentation;
- configured PNG/STL builds;
- build artifact upload;
- generated `build` branch publication.

The reusable verification workflow runs the generic source/build verification,
then project-specific `verification.commands`, and can publish the configured
verification output to the `verification` branch.

### Tooling version alignment

A consumer declares the expected tool release in `project.yml`:

```yaml
tooling:
  tool_scad_project:
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v0.6.0
```

For a release-pinned consumer, these three references should represent the same
release:

```text
project.yml tooling.tool_scad_project_version
Git submodule tools/tool.scad-project
reusable workflow @v0.6.0
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
  verification_branch: verification
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

## Standard generated build index

`scad-project build-index` writes the common root `bld/README.md`. It links only
to generated sections that actually exist (`design`, `png`, `stl`). This keeps
the `build` branch presentation consistent across libraries and consumer
projects.
