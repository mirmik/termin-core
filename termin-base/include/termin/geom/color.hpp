#pragma once

#include <tcbase/tcbase_api.h>

namespace termin {

    // Authored/display-referred RGBA encoded with the IEC sRGB transfer
    // function.  RGB is normally in [0, 1], while alpha is linear coverage.
    // This is intentionally a plain four-float value: encoding is part of the
    // type, not stored as runtime metadata.
    struct SrgbColor {
        float r;
        float g;
        float b;
        float a;
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

    // RGBA color with float components in [0, 1].
    struct Color4 {
        float r = 0.0f;
        float g = 0.0f;
        float b = 0.0f;
        float a = 1.0f;

        Color4() = default;
        Color4(float r, float g, float b, float a = 1.0f)
            : r(r),
              g(g),
              b(b),
              a(a) {}

        static Color4 black() {
            return {0, 0, 0, 1};
        }
        static Color4 white() {
            return {1, 1, 1, 1};
        }
        static Color4 red() {
            return {1, 0, 0, 1};
        }
        static Color4 green() {
            return {0, 1, 0, 1};
        }
        static Color4 blue() {
            return {0, 0, 1, 1};
        }
        static Color4 transparent() {
            return {0, 0, 0, 0};
        }
    };

} // namespace termin
