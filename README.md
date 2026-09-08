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
scad-project libraries-check
scad-project docs-lint
scad-project design-lint
scad-project design-render
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

libraries:
  - name: lib.scad.clamps
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
ghcr.io/brainboxemb/scad-toolchain:v0.3.0
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
