# tool.scad-project

Reusable SCAD project tooling for OpenSCAD/PythonSCAD build, design documentation,
verification, publication and release workflows.

## Architecture

`tool.scad-project` is no longer the generic repository bootstrap/dependency
manager. That responsibility is owned by
[`tool.git-project`](https://github.com/brainboxemb/tool.git-project).

```text
consumer repository
    │
    ├─ tools/tool.git-project
    │      generic bootstrap / dependency registration / status / update
    │
    ├─ project.yml
    │      generic project + profile + dependency policy
    │
    ├─ project.scad.yml
    │      SCAD-specific build/design/verification/publication policy
    │
    └─ tools/tool.scad-project
           SCAD CLI + reusable workflows
                  │
                  └─ docker.scad-toolchain
                         runtime capabilities
```

The split is deliberate: generic Git/submodule behavior should not be copied
back into this repository.

Release history: [`CHANGELOG.md`](CHANGELOG.md).

## Configuration

A current-generation consumer uses generic `project.yml` plus a SCAD profile.

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
    ref: <immutable-tag-or-full-commit>

  - name: lib.scad.clamps
    role: external
    type: git-submodule
    url: https://github.com/brainboxemb/lib.scad.clamps.git
    path: dsg/openscad/ext/lib.scad.clamps
    ref: <immutable-tag-or-full-commit>
```

`project.scad.yml`:

```yaml
paths:
  design_root: dsg/openscad
  build_root: bld
  render_root: dsg/openscad/render
  export_root: dsg/openscad/export

externals:
  - name: lib.scad.clamps
    required_file: openscad/tube-clamp/tube_clamp.scad

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

Dependency URL/path/ref/type come from generic `project.yml`. SCAD-only external
metadata such as `required_file` is matched by dependency name from the profile.
The loader composes both files into one internal SCAD configuration.

The older combined `project.yml` remains a compatibility input. Current-generation
consumers use the split model; removing the compatibility path is a later cleanup
and release decision.

See [`examples/project.yml`](examples/project.yml) and
[`examples/project.scad.yml`](examples/project.scad.yml).

## Bootstrap and dependency update

The bootstrap engine is `tools/tool.git-project`, pinned directly by the parent
repository gitlink. Root `bootstrap.ps1` / `bootstrap.sh` launchers come from
`tool.git-project`; they restore that exact bootstrap tool and then establish the
managed dependencies declared in `project.yml`.

`tool.scad-project` no longer contains a generic bootstrap implementation or a
second Git ref resolver.

A SCAD consumer can use the small wrappers in [`consumer/`](consumer/) for an
intentional dependency update:

```powershell
.\update-repo.ps1
```

```bash
bash ./update-repo.sh
```

Those wrappers call:

```text
scad-project repo-update
    ↓
tool.git-project update
    ↓
scad-project workflow-sync
```

The generic tool moves dependency gitlinks. The final `workflow-sync` step is
SCAD-specific: consumer Build, Verify and Release reusable-workflow calls are
rewritten to the exact checked-out `tool.scad-project` commit SHA.

Compatibility commands remain available:

```text
scad-project repo-sync      delegate generic bootstrap, then workflow-sync
scad-project repo-update    delegate generic update, then workflow-sync
scad-project repo-status    delegate generic status
scad-project workflow-sync  align SCAD reusable workflows only
```

`externals-init` and `externals-sync` are compatibility aliases for generic
bootstrap. `externals-deinit` is no longer a SCAD-owned Git mutation; generic
managed dependencies belong to `tool.git-project`.

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
scad-project build-audit
scad-project verify
scad-project produce-build
scad-project produce-verification
scad-project build-index
```

`config-lint` validates the generic `project.yml` through the pinned
`tool.git-project` when the split configuration model is active, then validates
SCAD-specific configuration locally.

`build` owns normal configured render/export output. `verify` is the separate
verification-domain action: it validates verification-relevant project source,
builds declared verification-only targets and then runs configured verification
commands. It does not materialize normal Build output as a side effect.

`build-audit` is an explicit post-build check for SCons consumers. It accepts an
existing structured build-decision report plus changed paths and checks whether a
reported outcome contradicts dependency impact that can be proven from the target's
recorded `sources`. Changed-path discovery itself stays outside the SCAD domain tool.
See [`docs/build-decision-audit.md`](docs/build-decision-audit.md).

`produce-build` and `produce-verification` are stable composite producer actions
for repository-level orchestrators. `produce-build` owns SCAD validation,
generated design documentation, normal configured output, build indexing and
producer provenance as one logical producer result. `produce-verification` owns
verification validation, verification-only targets/project checks and producer
provenance; it never invokes normal Build. GitHub/Moon cache restore, current
materialization evidence and generated-branch publication remain outside these
domain actions.

## Directory-based builds

Normal OpenSCAD build entrypoints can be discovered from configured directories:

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

Optional `render.yml` and `export.yml` files beside the entrypoints define size
variants, image sizes and output-name patterns. Explicit `builds:` mappings
remain available for exceptional source/output mappings.

## Selective SCons build engine

SCons is an optional internal backend behind the normal `scad-project build`
interface:

```yaml
build_engine:
  engine: scons
```

The direct backend remains available for compatible projects. Both backends use
the same target-discovery model.

The SCons backend tracks transitive OpenSCAD `use`/`include` dependencies and
literal `import()`/`surface()` leaf inputs. Dynamic file loading that cannot be
represented safely is rejected rather than silently creating stale output.

Normal build and verification maintain separate selective cache/state scopes.
Generated design documentation uses dependency-aware per-image SCons targets
when the exact whole-design snapshot is unavailable.

SCons build decisions are written as structured per-target telemetry with the
shared outcomes `BUILT`, `CACHE_RESTORED`, `CURRENT` and `ERROR`. Normal build,
generated-design and verification reports use the same schema, include output
existence before/after execution, source/dependency inputs, a stable target-spec
digest and available run/cache provenance. GitHub Actions Step Summaries use the
same vocabulary instead of the older ambiguous `cache/current` label.

See [`docs/build-decision-telemetry.md`](docs/build-decision-telemetry.md) for the
machine-readable report contract and classification rules, and
[`docs/build-decision-audit.md`](docs/build-decision-audit.md) for the independent
post-build consistency check.

## Design documentation

Source `design.md` is authoritative; generated documentation goes under:

```text
bld/design/project/...
bld/design/ext/<external-name>/...
```

Canonical render declarations use:

```text
scad-render-defaults
scad-render
```

Supported render engines are OpenSCAD and PythonSCAD. Explicit engine selection
wins over suffix inference.

A source-view declaration may use an existing module/view rather than duplicate
geometry in Markdown. Inline render snippets remain OpenSCAD-only.

Camera policy:

- orientation-only `vpr` may use autocenter/viewall;
- exact framing requires `vpr`, `vpt` and `vpd` together;
- prefer a dedicated detail view when unrelated geometry should be omitted.

`design.include_externals: false` suppresses generated external design docs but
does not remove external CAD source needed by builds.

## Source documentation

Structured `.scad` documentation follows upstream `openscad_docsgen` syntax.
A structured source begins with `File:` or `LibFile:` before Module/Function/etc.

```text
scad-project docs-lint
```

runs the upstream documentation check on project source.

## OpenSCAD warning policy

A zero exit code is not sufficient proof of valid geometry. Shared command
execution rejects warning/error classes that indicate undefined values or broken
geometry while allowing known benign presentation warnings.

## Render post-processing

Configured PNGs may receive a watermark:

```yaml
rendering:
  watermark:
    text: "© 2026 brainboxemb"
```

The generic image operation itself is supplied by `docker.scad-toolchain` as
`scad-image-watermark`; this repository owns only when it is invoked. STL output
is never watermarked.

## Verification

Verification-only OpenSCAD evidence can be declared separately from production
build output:

```yaml
verification:
  render_root: vrf/openscad/render
  export_root: vrf/openscad/export
  output_root: vrf/out
  commands:
    - [bash, scripts/run-project-checks.sh]
```

`scad-project verify` first performs the source/configuration checks required for
verification, then builds declared verification targets through the dedicated
verification SCons cache/state path, and finally runs project-specific commands.
Normal `bld/` output and the normal Build cache are outside this action.

Declared evidence is dependency-aware and uses a verification-specific SCons
cache. Project-specific commands run after declared verification targets and
should inspect/assert behavior rather than become a second target-orchestration
system.

## Publication

Recommended policy keeps generated content off the source branch:

```yaml
publication:
  production:
    source_branch: main
    build_branch: prod/build
    verification_branch: prod/verification
  development:
    pr_branch_prefix: dev/pr
  tags:
    pattern: "v*"
  release:
    branch_prefix: rel
    tag_pattern: "v*"
    changelog: CHANGELOG.md
```

Normal production builds publish mutable `prod/*` snapshots. Pull requests may
publish isolated `dev/pr-N/*` previews. Coordinated releases create immutable
release snapshots/assets from one exact source commit.

Every generated snapshot includes `publication-info.txt` with source, tooling
and runtime provenance.

## Reusable GitHub workflows

Consumers keep thin callers for:

```text
.github/workflows/project-build.yml
.github/workflows/project-verify.yml
.github/workflows/project-release.yml
```

External callers should be pinned to the exact checked-out tool commit, not a
moving branch and not an annotated tag. `workflow-sync` maintains these literal
SHAs after dependency updates.

The reusable workflows provide the common lint/design/build/cache/publication
sequence and run on the pinned `docker.scad-toolchain` image. Build and Verify
remain separate domain workflows: Verify owns only verification targets, commands,
evidence and its verification cache.

Repository-level orchestrators may instead bind their coarse tasks to
`produce-build` and `produce-verification`. Those commands provide the complete
SCAD producer boundary while SCons remains authoritative for fine-grained target
decisions whenever a producer task actually executes.

## Direct dependency rule

Normal repositories initialize only their own direct dependencies. Nested
submodules belonging to a consumed library's standalone development environment
are not recursively initialized by a parent consumer.

`actions/checkout` and SCAD-owned helper code must therefore remain
non-recursive unless a dedicated integration test explicitly proves a complete
dependency tree.

## Runtime

The runtime image and external CAD capabilities remain separate from this tool:

```text
ghcr.io/brainboxemb/scad-toolchain:<pinned release>
```

The image contains OpenSCAD, PythonSCAD, SCons and supporting commands. Exact
runtime versions are reported by `scad-toolchain-info` and publication
provenance.

## Development workflow

Normal changes use issue -> numbered feature branch -> draft PR -> evidence ->
review -> merge. See [`AGENTS.md`](AGENTS.md) for the authoritative repository
rules.

Cross-project architecture, repository classification and migration/rollout order are
coordinated from [`brainboxemb.meta`](https://github.com/brainboxemb/brainboxemb.meta).

The model, code and documentation are being developed with the assistance of
ChatGPT.
