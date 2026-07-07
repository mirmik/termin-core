#pragma once

#include "bounds2.hpp"

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

// 2D rectangle with floating-point origin and extent.
struct Rect2f {
    float x = 0.0f;
    float y = 0.0f;
    float width = 0.0f;
    float height = 0.0f;

    Rect2f() = default;
    Rect2f(float x, float y, float width, float height) : x(x), y(y), width(width), height(height) {}

    Bounds2f bounds() const { return {x, y, x + width, y + height}; }
};

} // namespace termin
