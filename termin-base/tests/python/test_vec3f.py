import pytest

from termin.geombase import Vec3, Vec3f, Vec3i


def test_vec3f_basic_api():
    v = Vec3f(1.0, 2.0, 3.0)

    assert len(v) == 3
    assert list(v) == pytest.approx([1.0, 2.0, 3.0])
    assert v.tolist() == pytest.approx([1.0, 2.0, 3.0])
    assert repr(v).startswith("Vec3f(")

    v[1] = 4.0
    assert v.y == pytest.approx(4.0)


def test_vec3f_math_and_conversions():
    a = Vec3f((1.0, 0.0, 0.0))
    b = Vec3f(0.0, 1.0, 0.0)

    assert a.dot(b) == pytest.approx(0.0)
    assert a.cross(b).approx_eq(Vec3f.unit_z())
    assert (a + b).approx_eq(Vec3f(1.0, 1.0, 0.0))
    assert (2.0 * a).approx_eq(Vec3f(2.0, 0.0, 0.0))
    assert a.normalized().approx_eq(a)

    as_double = Vec3f(1.0, 2.0, 3.0).to_double()
    assert isinstance(as_double, Vec3)
    assert as_double.tolist() == pytest.approx([1.0, 2.0, 3.0])

    assert Vec3i(1, 2, 3).to_float().approx_eq(Vec3f(1.0, 2.0, 3.0))
