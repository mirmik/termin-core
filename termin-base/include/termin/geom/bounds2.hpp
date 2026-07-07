#pragma once

#include "size2.hpp"

namespace termin {

// 2D bounds with integer min/max coordinates.
struct Bounds2i {
    int x0 = 0;
    int y0 = 0;
    int x1 = 0;
    int y1 = 0;

    Bounds2i() = default;
    Bounds2i(int x0, int y0, int x1, int y1) : x0(x0), y0(y0), x1(x1), y1(y1) {}

    int width() const { return x1 - x0; }
    int height() const { return y1 - y0; }

    static Bounds2i from_size(int width, int height) {
        return {0, 0, width, height};
    }
    static Bounds2i from_size(Size2i size) {
        return {0, 0, size.width, size.height};
    }
};

// 2D bounds with floating-point min/max coordinates.
struct Bounds2f {
    float x0 = 0.0f;
    float y0 = 0.0f;
    float x1 = 0.0f;
    float y1 = 0.0f;

    Bounds2f() = default;
    Bounds2f(float x0, float y0, float x1, float y1) : x0(x0), y0(y0), x1(x1), y1(y1) {}

    float width() const { return x1 - x0; }
    float height() const { return y1 - y0; }
};

} // namespace termin
