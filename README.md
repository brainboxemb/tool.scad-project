# tool.scad-project

Reusable workflow tooling for configuration-driven OpenSCAD projects.

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
  design_root: dsg/openscad
  build_root: bld

openscad:
  common_flags:
    - --enable=object-function
  render_flags:
    - --render
  image_size: [1600, 1000]

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


## Materialized design build

`design.md` is source documentation and remains on the normal code branch.
Generated images do not live beside it.

Run:

```text
scad-project design-build
```

The tool discovers design documents from both the project and configured
externals, renders their declared views, and creates a complete generated tree:

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

The generated `design.md` files are materialized copies. A source declaration
such as:

```markdown
<!-- scad-design
type: source-view
module: tube_design
view: bore
image: 02-bore.png
alt: Tube bore
-->
```

becomes:

```markdown
![Tube bore](img/02-bore.png)
```

in the build tree.

The source Markdown and external checkouts are never modified.

The complete design tree is staged first and only replaces `bld/design` after a
successful build, so a failed render does not destroy the previous local build.

### External design documentation

Configured externals are intentionally included. This means a consumer project
can build and browse the design documentation of a library dependency without
that library committing generated PNG files to its source branch.

The same library can generate the same documentation in its own repository.

## Generated build branch

Generated content belongs off the source branch.

`project.yml` may define:

```yaml
publication:
  build_branch: build
```

CI can then run:

```text
scad-project publish-build
```

which force-replaces a mutable orphan `build` branch with the current contents
of `bld/`.

The source branch therefore contains only source/configuration, while the build
branch contains materialized documentation, renders and exports.

`publish-build` is intended for authenticated CI. Pull requests should build
and upload artifacts but not publish the branch.


### Camera and image handling

A declaration may use `size: [width, height]`. A declaration containing only
`vpr` uses that orientation together with OpenSCAD auto-centering/view-all.
Use `vpr`, `vpt` and `vpd` together only when an exact camera is required.

Materialization also copies static files that already live next to a source
`design.md`. This keeps older external libraries readable while they migrate to
`scad-design` declarations. Missing legacy images in an external produce a
warning; missing project-owned images fail the build.
