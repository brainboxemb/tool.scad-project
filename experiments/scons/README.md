# SCons selective-build experiment

This experiment evaluates SCons as the dependency/signature engine behind the
existing `scad-project build` interface. It is deliberately not merged into the
production build path yet; the implementation remains on the experiment branch
while the integration behaviour is validated in `template.scad-project`.

## Why this lives here

The build policy belongs to `tool.scad-project`. `template.scad-project` remains
the integration/validation consumer, so a separate test repository is not
needed for this prototype.

A dedicated `test.scad-project` repository should only be introduced if later
integration cases become artificial enough that they would clutter the normal
template project.

## Runtime

SCons 4.11.1 is part of the immutable
`ghcr.io/brainboxemb/scad-toolchain:v0.4.1` image. The reusable build and
verification workflows consume that image directly; they do not install SCons
ad hoc.

The Actions cache namespace is intentionally conservative. It includes:

- repository identity;
- immutable SCAD toolchain version;
- exact checked-out `tool.scad-project` gitlink SHA;
- a hash of project configuration and design source inputs.

When only project inputs change, the primary Actions cache key changes but the
compatible restore prefix remains available. SCons then decides which targets
can be restored from `CacheDir` and which targets must execute again.

## What has been proved

Unit and subprocess tests in this repository prove the lower-level behaviour:

1. OpenSCAD `use` and `include` dependencies are discovered transitively.
2. Cycles, duplicates, relative project paths and external-library paths are
   handled deterministically.
3. Target specifications participate in SCons signatures.
4. A clean runner can hydrate unchanged outputs from a restored `CacheDir`.

The real integration experiment is `brainboxemb/template.scad-project` PR #3.
Using four configured outputs, it produced these results:

| Scenario | Result |
| --- | --- |
| Cold cache / clean runner | `targets=4 executed=4 not-executed=0` |
| Identical tree / fresh runner | `targets=4 executed=0 not-executed=4` |
| Only `components/tube/tube.scad` changed | `targets=4 executed=3 not-executed=1` |
| Temporary tube change reverted | `targets=4 executed=0 not-executed=4` |

For the selective dependency change, the tube PNG and assembly PNG/STL were
rebuilt, while the independent mounting-plate PNG was restored from cache. This
is the behaviour required before applying the mechanism to larger projects such
as the HUB75 frame.

## Current boundary

The dependency-aware backend currently covers configured `build` outputs only.
`design-build` is still a separate renderer and still regenerates all declared
design-documentation images on each workflow run. In the template integration
case that means 16 design renders still run even when all four configured build
outputs are cache hits.

Design-documentation rendering is therefore the next optimization area. It
should be made optional/selective independently rather than obscuring the now
proven configured-output behaviour.

## Test layout

- `tests/test_openscad_deps.py` unit-tests the scanner independently from SCons.
- `tests/test_scons_prototype.py` runs real SCons subprocesses against a small
  two-target SCAD fixture and simulates clean GitHub-hosted runners between
  invocations.
