#pragma once

#include "size2.hpp"
#include <cstddef>
#include <type_traits>

namespace termin {

    // 2D bounds with integer min/max coordinates.
    struct Bounds2i {
        int x0 = 0;
        int y0 = 0;
        int x1 = 0;
        int y1 = 0;

        Bounds2i() = default;
        Bounds2i(int x0, int y0, int x1, int y1)
            : x0(x0),
              y0(y0),
              x1(x1),
              y1(y1) {}

        int width() const {
            return x1 - x0;
        }
        int height() const {
            return y1 - y0;
        }

        static Bounds2i from_size(int width, int height) {
            return {0, 0, width, height};
        }
        static Bounds2i from_size(Size2i size) {
            return {0, 0, size.width, size.height};
        }
    };

    using Bounds2f = ::tc_bounds2f;

    static_assert(std::is_same<Bounds2f, ::tc_bounds2f>::value, "termin::Bounds2f must alias tc_bounds2f");
    static_assert(std::is_standard_layout<Bounds2f>::value, "Bounds2f must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Bounds2f>::value, "Bounds2f must stay trivially copyable");
    static_assert(sizeof(Bounds2f) == sizeof(float) * 4, "Bounds2f must stay a packed min/max tuple");
    static_assert(offsetof(Bounds2f, x0) == 0, "Bounds2f.x0 offset changed");
    static_assert(offsetof(Bounds2f, y0) == sizeof(float), "Bounds2f.y0 offset changed");
    static_assert(offsetof(Bounds2f, x1) == sizeof(float) * 2, "Bounds2f.x1 offset changed");
    static_assert(offsetof(Bounds2f, y1) == sizeof(float) * 3, "Bounds2f.y1 offset changed");

} // namespace termin
