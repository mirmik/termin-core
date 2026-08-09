#pragma once

#include <tcbase/tcbase_api.h>

namespace termin {

    // Authored/display-referred RGBA encoded with the IEC sRGB transfer
    // function.  RGB is normally in [0, 1], while alpha is linear coverage.
    // This is intentionally a plain four-float value: encoding is part of the
    // type, not stored as runtime metadata.
    struct SrgbColor {
        float r = 0.0f;
        float g = 0.0f;
        float b = 0.0f;
        float a = 1.0f;

        constexpr SrgbColor() = default;
        constexpr SrgbColor(float r_, float g_, float b_, float a_ = 1.0f) : r(r_), g(g_), b(b_), a(a_) {}

        static constexpr SrgbColor black() { return {0, 0, 0, 1}; }
        static constexpr SrgbColor white() { return {1, 1, 1, 1}; }
        static constexpr SrgbColor red() { return {1, 0, 0, 1}; }
        static constexpr SrgbColor green() { return {0, 1, 0, 1}; }
        static constexpr SrgbColor blue() { return {0, 0, 1, 1}; }
        static constexpr SrgbColor transparent() { return {0, 0, 0, 0}; }
    };

    // Renderer-working-space RGBA.  RGB is linear and may contain HDR values;
    // alpha remains linear.  No range restriction or implicit clamping is
    // performed by this value type.
    struct LinearColor {
        float r;
        float g;
        float b;
        float a;
    };

    TCBASE_API LinearColor srgb_to_linear(SrgbColor value) noexcept;
    TCBASE_API SrgbColor linear_to_srgb(LinearColor value) noexcept;

} // namespace termin
