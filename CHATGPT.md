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


## OpenSCAD warning policy

Do not treat OpenSCAD exit code 0 as sufficient proof of a valid render/build.

`run_checked()` captures combined stdout/stderr and rejects warning classes that
usually indicate broken geometry, including unknown variables, undefined
operations and invalid translate/rotate/etc parameter conversion.

The viewport message caused by explicit `$vpr/$vpt/$vpd` is benign and allowed.

When adding new warning handling, prefer a small explicit allow/fatal policy
over treating every OpenSCAD WARNING as fatal.



## Design image framing and legacy assets

Do not emit `$vpr/$vpt/$vpd` into temporary SCAD just to control design images.
A source-level `$vp*` disables OpenSCAD auto framing. Use CLI camera flags; `vpr`
alone means orientation plus `--autocenter --viewall`, while an exact camera
requires `vpr`, `vpt` and `vpd` together.

Generation copies static sibling assets for backward compatibility.
Generated declaration images overwrite same-named copied assets. External legacy
missing images warn; project-owned missing image links fail.

## Generated design documentation architecture

Source `design.md` files are authoritative. Never write generated design PNGs
back into project source directories or external checkouts.

Canonical authoring syntax:

```markdown
<!-- scad-render-defaults
module: example_design
vpr: [70, 0, 35]
-->

<!-- scad-render
view: base
-->
```

`scad-render` values override `scad-render-defaults`. Missing image names are
generated as `NN-<view>.png` from declaration order. `scad-design` is only a
temporary compatibility syntax for existing repositories.

Project-level design image size belongs in:

```yaml
openscad:
  design_image_size: [640, 480]
```

Normal build renders keep using `openscad.image_size`.

`design-build` writes only below:

```text
bld/design/project/...
bld/design/ext/<external-name>/...
```

The generated Markdown contains ordinary image references and omits authoring
metadata blocks. Build the complete generated design tree in staging first and
replace `bld/design` only after success.

Use user-facing wording such as "generated design documentation" and keep terminology simple.


## Multi-engine design rendering

`tool.scad-project` owns render dispatch for generated design documentation.

Supported engines:
- `openscad`
- `pythonscad`

Selection precedence:
1. per-render `engine`
2. `scad-render-defaults.engine`
3. source suffix inference (`.scad` -> OpenSCAD, `.py` -> PythonSCAD)
4. error if ambiguous

Do not equate source format with runtime architecture. PythonSCAD may consume
OpenSCAD libraries, so an explicit engine must always override suffix inference.

OpenSCAD source-view contract:
- source
- module
- view

PythonSCAD source-view contract:
- source/entrypoint
- view injected as `-D design_view=<value>`

Run PythonSCAD renders from the entrypoint directory so sibling Python imports
work naturally.

Inline render snippets are OpenSCAD-only until an explicit Python inline format
is designed.


## Reusable workflow convention

`tool.scad-project` owns the standard reusable GitHub workflows:

```text
.github/workflows/project-build.yml
.github/workflows/project-verify.yml
```

Consumer repositories should contain only thin caller workflows and pin them to
a release tag. Do not duplicate the standard lint/design/build/publication step
sequence in each consumer unless there is a project-specific reason.

The local Git submodule and reusable workflow are two views of the same tooling
release. Consumer updates should move these together:

```text
project.yml tooling.tool_scad_project_version
.gitlink tools/tool.scad-project
workflow uses: ...@vX.Y.Z
```

`SCAD_PROJECT_WORKFLOW_VERSION` is set by the reusable workflow and checked by
`tooling-check` against both project config and the running local CLI.

## Canonical bootstrap source

`bootstrap/bootstrap.ps1` and `bootstrap/bootstrap.sh` are the canonical source
for consumer root bootstrap files.

Required behavior:
- support a missing parent directory such as `tools/`;
- register a missing gitlink using `.gitmodules` URL/path;
- preserve a valid existing checkout;
- fail on conflicting non-Git content;
- restore pinned commits with `submodule update --init --recursive`;
- validate mode `160000` for every declared gitlink before reporting success.

Do not maintain project-specific bootstrap implementations when the canonical
script can be copied unchanged.

## Generated branch standardization

`build-index` owns the common root README for the mutable `build` branch.
Consumers should not hand-author different build-branch index text in their CI.

`project-verify.yml` is optional and intended only for projects with genuine
functional verification evidence. `verification.commands` remain project
specific while orchestration/publication remains generic.
