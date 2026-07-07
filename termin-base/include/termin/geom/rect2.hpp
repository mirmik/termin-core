#pragma once

namespace termin {

// 2D rectangle with integer origin and extent.
struct Rect2i {
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;

    Rect2i() = default;
    Rect2i(int x, int y, int width, int height) : x(x), y(y), width(width), height(height) {}
};

} // namespace termin
