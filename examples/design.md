# Example design

<!-- scad-design
type: source-view
module: example_design
view: base
image: 01-base.png
vpr: [70, 0, 35]
-->

<!-- scad-design
type: inline
image: 02-wall-thickness.png
-->

```openscad
linear_extrude(height=2)
difference() {
    circle(d=20);
    circle(d=16);
}
```
