#pragma once

namespace termin {

// 2D size with integer components.
struct Size2i {
    int width = 0;
    int height = 0;

    Size2i() = default;
    Size2i(int w, int h) : width(w), height(h) {}

    bool operator==(const Size2i& other) const {
        return width == other.width && height == other.height;
    }
    bool operator!=(const Size2i& other) const {
        return !(*this == other);
    }
};

} // namespace termin
