from pathlib import Path

from scad_project.design import (
    DesignDocument,
    DesignRender,
    _camera_args,
    _copy_source_assets,
)


def _render(**overrides):
    values = dict(
        document=DesignDocument(Path('/tmp/design.md'), 'project', Path('x/design/design.md')),
        block_start=0,
        block_end=1,
        kind='inline',
        image='view.png',
        alt='View',
        source=None,
        module=None,
        view=None,
        inline_code='cube(1);',
        vpr=None,
        vpt=None,
        vpd=None,
        size=None,
    )
    values.update(overrides)
    return DesignRender(**values)


def test_vpr_only_uses_camera_orientation_and_auto_fit():
    args = _camera_args(_render(vpr=[70.0, 0.0, 35.0]))
    assert '--autocenter' in args
    assert '--viewall' in args
    assert any(arg.startswith('--camera=') for arg in args)


def test_exact_camera_does_not_auto_fit():
    args = _camera_args(
        _render(vpr=[70.0, 0.0, 35.0], vpt=[1.0, 2.0, 3.0], vpd=400.0)
    )
    assert '--autocenter' not in args
    assert '--viewall' not in args


def test_materialization_copies_static_design_assets(tmp_path: Path):
    source_dir = tmp_path / 'source' / 'design'
    source_dir.mkdir(parents=True)
    source_doc = source_dir / 'design.md'
    source_doc.write_text('# Design\n', encoding='utf-8')
    (source_dir / 'img').mkdir()
    (source_dir / 'img' / 'legacy.png').write_bytes(b'legacy')

    out_doc = tmp_path / 'build' / 'design.md'
    out_doc.parent.mkdir(parents=True)
    document = DesignDocument(source_doc, 'external', Path('design/design.md'), 'example')

    _copy_source_assets(document, out_doc)

    assert (out_doc.parent / 'img' / 'legacy.png').read_bytes() == b'legacy'
