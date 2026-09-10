"""OpenSCAD warning handling

Checks:
OpenSCAD warnings that indicate broken geometry or calculations, such as an unknown
variable or undefined operation, fail the build. The known viewport warning caused by
explicit camera settings is allowed.

Testing approach:
The tests pass representative OpenSCAD output strings directly to the real warning
checker. This isolates the warning policy from OpenSCAD itself: no process is started
because only classification of already-produced output is under test.
"""

import pytest

from scad_project.process import _check_openscad_output


def test_unknown_variable_warning_is_fatal():
    with pytest.raises(RuntimeError):
        _check_openscad_output(
            ["openscad", "-o", "out.png", "model.scad"],
            'WARNING: Ignoring unknown variable "X" in file model.scad, line 10\n',
        )


def test_undefined_operation_warning_is_fatal():
    with pytest.raises(RuntimeError):
        _check_openscad_output(
            ["xvfb-run", "-a", "openscad", "-o", "out.png", "model.scad"],
            "WARNING: undefined operation (undefined + number) in file model.scad\n",
        )


def test_viewport_warning_is_allowed():
    _check_openscad_output(
        ["xvfb-run", "-a", "openscad", "-o", "out.png", "model.scad"],
        "WARNING: Viewall and autocenter disabled in favor of $vp*\n",
    )
