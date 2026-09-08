# ChatGPT handoff

## Purpose

`tool.scad-project` is the reusable project-workflow layer between the runtime
toolchain and concrete CAD projects.

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

## Configuration-first rule

Project-specific declarations belong in root `project.yml`.

Prefer extending configuration over adding project-specific shell scripts.

## Design documentation

Preferred layout:

```text
dsg/openscad/components/<component>/
├── <component>.scad
└── design/
    ├── design.md
    └── img/
```

Preferred render declaration:

```markdown
<!-- scad-design
type: source-view
module: component_design
view: step-name
image: 01-step.png
-->
```

Source-view is preferred because reusable geometry stays in `.scad`.

Inline OpenSCAD is allowed for small documentation-only illustrations. The
governing rule is to avoid unnecessary code duplication.

## Render safety

For design images:

1. parse/lint all declarations;
2. calculate complete expected image set;
3. render every expected image;
4. verify outputs exist and are non-empty;
5. only then remove stale PNGs.

## Source/API comments

Use upstream `openscad_docsgen` syntax for structured `.scad` comments.

A structured file must declare `File:` or `LibFile:` before `Module`,
`Function`, `Constant`, etc.

Keep API documentation and design documentation separate:

```text
.scad docsgen comments -> API/source reference
design.md               -> design intent and visual explanation
```

## Toolchain baseline

`ghcr.io/brainboxemb/scad-toolchain:v0.3.0`

## v0.1.0 scope

Initial commands:

```text
config-lint
libraries-check
docs-lint
design-lint
design-render
build
verify
```

Do not yet add copyright/watermark processing, verification branch publishing,
or Docker embedding. First validate this interface using `template.scad-project`.
