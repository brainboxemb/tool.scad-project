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

## Publication-context rule

Publication behavior is resolved centrally from the GitHub source context.

- production branch: publish mutable `build` / `verification`;
- non-production branch: publish mutable shared `dev/build` / `dev/verification`;
- pull request: artifact-only;
- version tag: artifact-only in v0.6.1.

Do not add branch-specific temporary workflows or edit `project.yml` merely to
redirect one development branch. Projects declare the branch names once; the
tool resolves the active destination.

Every generated build/verification artifact and mutable branch snapshot must
contain `publication-info.txt` with source, tooling and runtime provenance.

This file is the current-generation replacement for the classic
`openscad-build.txt`. Do not reintroduce separate engine-specific build-info
files unless a future requirement cannot be represented in the unified record.

Required layers:

```text
Source
    repository / ref / commit / workflow

Tooling
    SCAD_TOOLCHAIN_IMAGE
    SCAD_TOOLCHAIN_VERSION
    SCAD_PROJECT_WORKFLOW_VERSION

Runtime components
    scad-toolchain-info output
```

The immutable Docker image is the primary runtime version pin. Exact OpenSCAD
and other component versions remain diagnostic evidence supplied by
`scad-toolchain-info`.


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

`ghcr.io/brainboxemb/scad-toolchain:v0.4.0`

## PNG watermark orchestration

Image processing belongs in `docker.scad-toolchain`; project policy and
orchestration belong in this repository.

Supported configuration:

```yaml
rendering:
  watermark:
    text: "© 2026 brainboxemb"
```

Rules:

- omit `rendering.watermark` to disable watermarking;
- if present, `text` must be a non-empty string;
- apply it only to configured PNG build outputs;
- render to a temporary unwatermarked PNG first;
- call the public `scad-image-watermark` command from the toolchain;
- verify the final PNG exists and is non-empty;
- remove the temporary PNG after processing;
- do not import Pillow or duplicate watermark drawing code here;
- do not watermark STL or generated design-documentation images unless that
  becomes an explicit future policy.

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


## Tool release workflow

Use the permanent workflow:

```text
.github/workflows/release.yml
```

A normal release is started through `workflow_dispatch` with:

```text
version
    immutable semantic tag, e.g. v0.6.1

release_sha
    exact already-verified commit SHA
```

The workflow validates that the requested version matches the package version in
`pyproject.toml`, refuses to overwrite an existing tag, creates an annotated
tag on the explicit release commit, and then explicitly dispatches
`.github/workflows/test.yml` on that tag.

The explicit dispatch is required because a tag pushed with `GITHUB_TOKEN`
does not itself create a follow-up workflow run.

If the connected GitHub interface cannot directly invoke `workflow_dispatch`,
do **not** tell the user they must start the release manually. Use the established
one-shot dispatcher pattern instead:

1. create a temporary `.github/workflows/_dispatch-release-vX.Y.Z.yml` on
   `main`;
2. make that workflow trigger only on the commit that introduces the helper;
3. give it `actions: write` and use `GITHUB_TOKEN` + `gh api` only to dispatch
   the permanent `release.yml` with `version` and the exact verified
   `release_sha`;
4. never duplicate tag creation/version validation in the helper;
5. after the permanent Release workflow has started, delete the temporary
   dispatcher from `main`;
6. accept the release only after the tagged `test.yml` run is green.

This workaround has been used successfully in this repository family and is the
preferred connected-GitHub release path whenever direct dispatch is unavailable.

A release is accepted only after the tagged `test.yml` run is green.

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


## Versioned dependency policy (v0.6.1)

`project.yml` is the dependency-policy source. Parent gitlinks are the resolved
lock.

Preferred tooling form:

```yaml
tooling:
  tool_scad_project:
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v0.6.1
```

External libraries also carry their own `ref`.

Supported values:
- exact tag, e.g. `v0.7.2`;
- `latest`, meaning highest stable semantic-version tag;
- branch name, e.g. `main`.

Do not interpret `latest` as the default branch.

Command semantics:
- `repo-sync`: restore committed gitlinks only; do not advance floating refs.
- `repo-update`: intentionally resolve refs and advance gitlinks.
- `repo-status`: report policy + locked/current commit.

This distinction preserves reproducible clones while allowing a project to opt
individual dependencies into `latest` or `main`.

`repo-update` updates libraries before `tool.scad-project` itself and leaves all
changes uncommitted. When tooling is updated, thin reusable workflow callers
are rewritten to the resolved literal workflow ref.

Canonical convenience wrappers:
- `update-repo.ps1`
- `update-repo.sh`

Consumer repositories may copy these to their root.


## Python-free update-repo layer

The canonical `update-repo.ps1` / `update-repo.sh` scripts must remain
Python-free, like bootstrap. They may parse only the `tooling` and `externals`
subset of `project.yml`.

Do not replace them with wrappers around `scad-project repo-update`; dependency
management must work before Python is installed.

## Direct-only submodule rule (v0.6.1)

Normal repository operations must initialize/update only direct dependencies.

Do not use `git submodule ... --recursive` in:
- bootstrap;
- update-repo;
- repo-sync/repo-update;
- externals-init/externals-sync;
- reusable consumer build/verify workflows.

A dependency's own submodules are development dependencies of that repository
and are initialized only when that repository acts as the standalone project.

Recursive checkout is allowed only in a dedicated integration test explicitly
designed to validate complete nested dependency trees.

