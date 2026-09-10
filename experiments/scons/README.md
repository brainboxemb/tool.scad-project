# SCons selective-build validation record

This directory records the validation work that led to the production SCons
backend in `tool.scad-project` v0.8.0. The user-facing command remains
`scad-project build`; SCons is an internal dependency/signature engine selected
through project configuration.

## Architecture

Build policy belongs to `tool.scad-project`. `template.scad-project` remains the
integration/validation consumer, so a separate test repository is not needed at
this stage. A dedicated `test.scad-project` repository should only be introduced
if later integration cases become artificial enough that they would clutter the
normal template project.

SCons 4.11.1 is part of immutable
`ghcr.io/brainboxemb/scad-toolchain:v0.4.1`. Reusable Build/Verify workflows use
that runtime directly and do not install SCons ad hoc.

The SCons backend deliberately consumes the same target list as the direct
backend. There is no second render/export configuration model.

## Dependency model

The OpenSCAD scanner is small and independently unit-tested. It:

- follows `use <...>` and `include <...>` transitively;
- treats literal `import()` and `surface()` file inputs as leaf dependencies;
- resolves relative project and configured external-library paths;
- handles comments, duplicates and cycles deterministically;
- fails safe on unresolved or dynamic file-loading expressions instead of
  silently accepting an incomplete cache signature.

## Cache model

The Actions cache namespace includes repository identity, immutable SCAD
runtime version, the exact checked-out `tool.scad-project` gitlink SHA and a hash
of relevant project build inputs. A compatible restore prefix keeps older SCons
objects available when only project inputs change; SCons then decides which
outputs are still valid.

Only SCons `CacheDir` data needs to persist. `bld/` and `.sconsign` can be absent
on the next GitHub-hosted runner: valid missing outputs are hydrated by build
signature.

## Integration evidence

The real integration experiment was `brainboxemb/template.scad-project` PR #3.
Using four configured OpenSCAD outputs it produced:

| Scenario | Result |
| --- | --- |
| Cold cache / clean runner | `targets=4 executed=4 not-executed=0` |
| Identical tree / fresh runner | `targets=4 executed=0 not-executed=4` |
| Only `components/tube/tube.scad` changed | `targets=4 executed=3 not-executed=1` |
| Temporary tube change reverted | `targets=4 executed=0 not-executed=4` |

For the selective change, the tube PNG and assembly PNG/STL were rebuilt while
the independent mounting-plate PNG was restored from cache. The temporary tube
change was reverted and does not remain in the final consumer tree.

## Generated design documentation

Design documentation remains separate from the per-target SCons graph. The
reusable Build workflow uses a whole-tree Actions cache for `bld/design`.

The template validation proved both sides of that policy:

1. a cold design-cache run generated the 16 project design images and stored the
   complete generated design tree;
2. an identical-tree run on a fresh runner restored `bld/design`, skipped
   `design-build` completely, and simultaneously restored all four configured
   build outputs without OpenSCAD execution.

Any changed design input currently invalidates the whole generated-design cache.
Per-document design dependency selection is deliberately deferred until there
is evidence that its additional complexity provides worthwhile savings.

## Test layout

- `tests/test_openscad_deps.py` covers the scanner independently from SCons.
- `tests/test_scons_prototype.py` runs real SCons subprocesses against a small
  two-target SCAD fixture and simulates clean GitHub-hosted runners.
- `tests/test_build_engine.py` and `tests/test_build_engine_config.py` cover the
  selectable production backend and its configuration contract.
- `tests/test_cache_workflows.py` guards the reusable workflow cache inputs.
