# Example design

The project-level default for generated design images comes from:

```yaml
openscad:
  design_image_size: [640, 480]
```

A design document can override that default for all of its renders with
`size:` in `scad-render-defaults`, and an individual `scad-render` can override
both. The precedence is therefore:

```text
scad-render size
    ↓
scad-render-defaults size
    ↓
project.yml openscad.design_image_size
    ↓
project.yml openscad.image_size
```

`size` controls the PNG canvas dimensions and aspect ratio. It does **not**
zoom into the model. Use `vpt`/`vpd`, or a purpose-built detail view, when the
feature itself needs different framing.

<!-- scad-render-defaults
module: example_design
vpr: [70, 0, 35]
-->

## Base

This uses the project-level design image size.

<!-- scad-render
view: base
-->

## Final

This also uses the project-level design image size.

<!-- scad-render
view: final
-->

## Detail with a different image size

A single image can choose a different canvas size without changing the project
default:

<!-- scad-render
view: detail
size: [800, 600]
-->

For a wide detail, changing the aspect ratio is equally valid:

<!-- scad-render
view: wide-detail
size: [960, 480]
-->
