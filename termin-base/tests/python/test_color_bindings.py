import math

from tcbase._geom_native import LinearColor, SrgbColor, linear_to_srgb, srgb_to_linear


def test_color_bindings_expose_typed_values_and_conversion():
    authored = SrgbColor(0.5, 0.25, 1.0, 0.5)
    assert tuple(authored) == (0.5, 0.25, 1.0, 0.5)
    assert authored.tolist() == (0.5, 0.25, 1.0, 0.5)

    linear = srgb_to_linear(authored)
    assert isinstance(linear, LinearColor)
    assert math.isclose(linear.r, 0.21404114, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(linear.g, 0.05087609, rel_tol=0.0, abs_tol=1e-6)
    assert linear.a == authored.a

    round_trip = linear_to_srgb(linear)
    assert isinstance(round_trip, SrgbColor)
    assert all(math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
               for actual, expected in zip(round_trip, authored, strict=True))


def test_linear_color_preserves_hdr_components_and_alpha():
    value = LinearColor(4.0, 0.5, -1.0, 0.25)
    assert tuple(value) == (4.0, 0.5, -1.0, 0.25)
    encoded = linear_to_srgb(value)
    assert math.isclose(encoded.r, 1.8247962, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(encoded.g, 0.73535698, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(encoded.b, -1.0, rel_tol=0.0, abs_tol=1e-6)
    assert encoded.a == 0.25
