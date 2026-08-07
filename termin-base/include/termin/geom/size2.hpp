#pragma once

#include <cstddef>
#include <tcbase/tc_types.h>
#include <type_traits>

namespace termin {

    using Size2f = ::tc_size2f;

    // 2D size with integer components.
    struct Size2i {
        int width = 0;
        int height = 0;

        Size2i() = default;
        Size2i(int w, int h)
            : width(w),
              height(h) {}

        bool operator==(const Size2i& other) const {
            return width == other.width && height == other.height;
        }
        bool operator!=(const Size2i& other) const {
            return !(*this == other);
        }
    };

    static_assert(std::is_same<Size2f, ::tc_size2f>::value, "termin::Size2f must alias tc_size2f");
    static_assert(std::is_standard_layout<Size2f>::value, "Size2f must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Size2f>::value, "Size2f must stay trivially copyable");
    static_assert(sizeof(Size2f) == sizeof(float) * 2, "Size2f must stay a packed width/height tuple");
    static_assert(offsetof(Size2f, width) == 0, "Size2f.width offset changed");
    static_assert(offsetof(Size2f, height) == sizeof(float), "Size2f.height offset changed");

} // namespace termin
