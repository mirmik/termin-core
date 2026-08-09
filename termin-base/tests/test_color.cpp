#include <cmath>
#include <type_traits>

#include <termin/geom/color.hpp>

#include "guard_main.h"

TEST_CASE("SrgbColor and LinearColor are distinct standard-layout values") {
    static_assert(std::is_standard_layout_v<termin::SrgbColor>);
    static_assert(std::is_standard_layout_v<termin::LinearColor>);
    static_assert(sizeof(termin::SrgbColor) == sizeof(float) * 4);
    static_assert(sizeof(termin::LinearColor) == sizeof(float) * 4);
    static_assert(!std::is_same_v<termin::SrgbColor, termin::LinearColor>);
    static_assert(!std::is_convertible_v<termin::SrgbColor, termin::LinearColor>);
    static_assert(!std::is_convertible_v<termin::LinearColor, termin::SrgbColor>);
}

TEST_CASE("sRGB conversions use IEC transfer and preserve alpha") {
    const termin::LinearColor linear = termin::srgb_to_linear({0.0f, 0.5f, 1.0f, 0.25f});

    CHECK(std::abs(linear.r - 0.0f) < 1.0e-7f);
    CHECK(std::abs(linear.g - 0.21404114f) < 1.0e-6f);
    CHECK(std::abs(linear.b - 1.0f) < 1.0e-7f);
    CHECK(linear.a == 0.25f);

    const termin::SrgbColor encoded = termin::linear_to_srgb(linear);
    CHECK(std::abs(encoded.r - 0.0f) < 1.0e-7f);
    CHECK(std::abs(encoded.g - 0.5f) < 1.0e-6f);
    CHECK(std::abs(encoded.b - 1.0f) < 1.0e-7f);
    CHECK(encoded.a == 0.25f);
}

TEST_CASE("sRGB conversions do not clamp HDR or signed components") {
    const termin::LinearColor hdr = termin::srgb_to_linear({2.0f, -0.5f, 0.1f, 2.0f});
    CHECK(hdr.r > 1.0f);
    CHECK(hdr.g < 0.0f);
    CHECK(hdr.a == 2.0f);

    const termin::SrgbColor round_trip = termin::linear_to_srgb(hdr);
    CHECK(std::abs(round_trip.r - 2.0f) < 1.0e-5f);
    CHECK(std::abs(round_trip.g + 0.5f) < 1.0e-6f);
    CHECK(std::abs(round_trip.b - 0.1f) < 1.0e-6f);
    CHECK(round_trip.a == 2.0f);
}

TEST_CASE("sRGB decoding follows the IEC piecewise boundary") {
    const termin::LinearColor below = termin::srgb_to_linear({0.04044f, 0.0f, 0.0f, 1.0f});
    const termin::LinearColor at = termin::srgb_to_linear({0.04045f, 0.0f, 0.0f, 1.0f});
    const termin::LinearColor above = termin::srgb_to_linear({0.04046f, 0.0f, 0.0f, 1.0f});

    CHECK(std::abs(below.r - (0.04044f / 12.92f)) < 1.0e-8f);
    CHECK(std::abs(at.r - (0.04045f / 12.92f)) < 1.0e-8f);
    CHECK(std::abs(above.r - std::pow((0.04046f + 0.055f) / 1.055f, 2.4f)) < 1.0e-8f);
    CHECK(below.r < at.r);
    CHECK(at.r < above.r);
}

TEST_CASE("sRGB encoding follows the IEC piecewise boundary") {
    const termin::SrgbColor below = termin::linear_to_srgb({0.0031307f, 0.0f, 0.0f, 1.0f});
    const termin::SrgbColor at = termin::linear_to_srgb({0.0031308f, 0.0f, 0.0f, 1.0f});
    const termin::SrgbColor above = termin::linear_to_srgb({0.0031309f, 0.0f, 0.0f, 1.0f});

    CHECK(std::abs(below.r - (0.0031307f * 12.92f)) < 1.0e-8f);
    CHECK(std::abs(at.r - (0.0031308f * 12.92f)) < 1.0e-8f);
    CHECK(std::abs(above.r - (1.055f * std::pow(0.0031309f, 1.0f / 2.4f) - 0.055f)) < 1.0e-8f);
    CHECK(below.r < at.r);
    CHECK(at.r < above.r);
}

GUARD_TEST_MAIN();
