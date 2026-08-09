#include <cmath>

#include <termin/geom/color.hpp>
#include <geom/tc_color.h>

namespace termin {
    namespace {
        // IEC sRGB is specified for non-negative components.  Extending the
        // transfer symmetrically to negative values keeps conversion total,
        // avoids an implicit clamp, and preserves signed HDR/intermediate
        // values when callers use the plain value type outside its usual
        // display-referred range.
        float srgb_channel_to_linear(float value) noexcept {
            const float magnitude = std::fabs(value);
            const float decoded = magnitude <= 0.04045f
                                      ? magnitude / 12.92f
                                      : std::pow((magnitude + 0.055f) / 1.055f, 2.4f);
            return std::copysign(decoded, value);
        }

        float linear_channel_to_srgb(float value) noexcept {
            const float magnitude = std::fabs(value);
            const float encoded = magnitude <= 0.0031308f
                                      ? magnitude * 12.92f
                                      : 1.055f * std::pow(magnitude, 1.0f / 2.4f) - 0.055f;
            return std::copysign(encoded, value);
        }
    } // namespace

    LinearColor srgb_to_linear(SrgbColor value) noexcept {
        return {
            srgb_channel_to_linear(value.r),
            srgb_channel_to_linear(value.g),
            srgb_channel_to_linear(value.b),
            value.a,
        };
    }

    SrgbColor linear_to_srgb(LinearColor value) noexcept {
        return {
            linear_channel_to_srgb(value.r),
            linear_channel_to_srgb(value.g),
            linear_channel_to_srgb(value.b),
            value.a,
        };
    }
} // namespace termin

extern "C" tc_linear_color tc_srgb_to_linear(tc_srgb_color value) {
    const termin::LinearColor converted = termin::srgb_to_linear({value.r, value.g, value.b, value.a});
    return {converted.r, converted.g, converted.b, converted.a};
}

extern "C" tc_srgb_color tc_linear_to_srgb(tc_linear_color value) {
    const termin::SrgbColor converted = termin::linear_to_srgb({value.r, value.g, value.b, value.a});
    return {converted.r, converted.g, converted.b, converted.a};
}
