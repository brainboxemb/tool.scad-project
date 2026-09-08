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

## v0.2.0 scope

Initial commands:

```text
config-lint
externals-check
externals-status
externals-init
externals-sync
externals-deinit
docs-lint
design-lint
design-render
build
verify
```

Do not yet add copyright/watermark processing, verification branch publishing,
or Docker embedding. First validate this interface using `template.scad-project`.


## Bootstrap architecture

The consumer project should pin this repository as:

```text
tools/tool.scad-project
```

Do not require a network pip install for normal project use.

Official bootstrap source files live in this repo:

```text
bootstrap/bootstrap.ps1
bootstrap/bootstrap.sh
```

A project copies the bootstrap file to its root. Bootstrap is intentionally
small and has only one special responsibility that cannot be delegated to the
tool itself: making `tools/tool.scad-project` available.

Bootstrap chain:

```text
consumer bootstrap.ps1
    -> register/init tools/tool.scad-project submodule
    -> local scad-project launcher
    -> externals-init
    -> remaining configured project submodules
```

Local launchers:

```text
scad-project.ps1
scad-project.sh
```

They execute `scad_project` from the checked-out `src/` tree using PYTHONPATH,
so the tool package itself does not need to be pip-installed.

## External schema and semantics

New projects use:

```yaml
externals:
  - name: ...
    type: git-submodule
    url: ...
    path: ...
    required_file: ...
```

The old `libraries:` key is accepted only as a migration compatibility path.

Commands:

```text
externals-init
externals-sync
externals-status
externals-check
externals-deinit
```

Semantics matter:

- `init`: add missing configured git submodules, then initialize recursively.
- `sync`: restore/configure the exact parent-repo-pinned gitlink commits.
- `status`: report local state and current commit.
- `check`: validate availability/required files.
- `deinit`: remove local checkout only; preserve `.gitmodules` and gitlink.

Do not make `deinit` equivalent to `git rm`. Repository-level removal is a
different destructive operation and should be an explicit future command.


## Shell launcher portability

Do not rely on the executable bit of `.sh` files in consumer repositories.
Projects are frequently created/extracted on Windows, where Git mode metadata
may not be preserved as expected.

In CI/bootstrap, invoke shell launchers explicitly:

```text
bash ./scad-project.sh ...
bash tools/tool.scad-project/scad-project.sh ...
```

The scripts may still be marked executable in this repository, but correctness
must not depend on that bit.


## Bootstrap hard requirement: no Python

Bootstrap must work before Python or the `scad-project` CLI is available.

Allowed dependencies:

```text
PowerShell/bash
Git
```

The consumer template carries `.gitmodules`. Bootstrap reads it directly using
`git config -f .gitmodules`, then ensures each configured path has a real
parent-repository gitlink.

The script is intentionally idempotent/recovery-oriented:
- correct gitlink -> keep;
- registered but uninitialized -> `submodule update --init`;
- `.gitmodules` entry but missing gitlink -> `submodule add --force`;
- interrupted checkout already present as Git working tree -> reuse;
- unrelated non-Git files occupying a submodule path -> stop with a clear error.

Do not call `scad-project externals-init` from bootstrap. That would reintroduce
the Python bootstrap dependency.

After bootstrap, normal project operations may use the local Python tool.

