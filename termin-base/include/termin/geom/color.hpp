#pragma once

namespace termin {

// RGBA color with float components in [0, 1].
struct Color4 {
    float r = 0.0f;
    float g = 0.0f;
    float b = 0.0f;
    float a = 1.0f;

    Color4() = default;
    Color4(float r, float g, float b, float a = 1.0f) : r(r), g(g), b(b), a(a) {}

    static Color4 black() { return {0, 0, 0, 1}; }
    static Color4 white() { return {1, 1, 1, 1}; }
    static Color4 red() { return {1, 0, 0, 1}; }
    static Color4 green() { return {0, 1, 0, 1}; }
    static Color4 blue() { return {0, 0, 1, 1}; }
    static Color4 transparent() { return {0, 0, 0, 0}; }
};

} // namespace termin
