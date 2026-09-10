# SCons selective-build experiment

This experiment evaluates SCons as the dependency/signature engine behind the
existing `scad-project build` interface. It is deliberately not wired into the
production build command yet.

## Why this lives here

The build policy belongs to `tool.scad-project`. `template.scad-project` remains
the integration/validation consumer, so a separate test repository is not
needed for the first prototype.

A dedicated `test.scad-project` repository should only be introduced if later
integration cases become artificial enough that they would clutter the normal
template project.

## Prototype questions

The first prototype must prove all of these before production integration:

1. OpenSCAD `use` and `include` dependencies are discovered transitively.
2. Cycles, duplicates, relative project paths and external-library paths are
   handled deterministically.
3. SCons invalidates only targets whose dependency signatures changed.
4. On a clean runner with an empty `bld/` and no `.sconsign` state, a restored
   SCons `CacheDir` can hydrate unchanged outputs so publication still receives
   a complete snapshot.
5. A changed nested dependency rebuilds only its affected target while other
   outputs are restored from the cache.

## Test layout

- `tests/test_openscad_deps.py` unit-tests the scanner independently from SCons.
- `tests/test_scons_prototype.py` runs real SCons subprocesses against a small
  two-target SCAD fixture and simulates clean GitHub-hosted runners between
  invocations.

SCons is kept in the optional `scons` dependency group during the experiment.
It should not become a production dependency or be added to
`docker.scad-toolchain` until the prototype has demonstrated a useful CI path.
