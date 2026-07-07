from termin.geombase import Bounds2f


def test_bounds2f_python_binding_preserves_min_max_order():
    bounds = Bounds2f(-2.0, -1.0, 2.0, 1.0)

    assert bounds.x0 == -2.0
    assert bounds.y0 == -1.0
    assert bounds.x1 == 2.0
    assert bounds.y1 == 1.0
    assert bounds.width() == 4.0
    assert bounds.height() == 2.0
    assert list(bounds) == [-2.0, -1.0, 2.0, 1.0]
    assert bounds.tolist() == [-2.0, -1.0, 2.0, 1.0]
    assert bounds == bounds.copy()
