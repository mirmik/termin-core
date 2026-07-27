#pragma once

#include <cstddef>
#include <type_traits>
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

using Rect2f = ::tc_rect2f;

static_assert(std::is_same<Rect2f, ::tc_rect2f>::value, "termin::Rect2f must alias tc_rect2f");
static_assert(std::is_standard_layout<Rect2f>::value, "Rect2f must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Rect2f>::value, "Rect2f must stay trivially copyable");
static_assert(sizeof(Rect2f) == sizeof(float) * 4, "Rect2f must stay a packed origin/extent tuple");
static_assert(offsetof(Rect2f, x) == 0, "Rect2f.x offset changed");
static_assert(offsetof(Rect2f, y) == sizeof(float), "Rect2f.y offset changed");
static_assert(offsetof(Rect2f, width) == sizeof(float) * 2, "Rect2f.width offset changed");
static_assert(offsetof(Rect2f, height) == sizeof(float) * 3, "Rect2f.height offset changed");

} // namespace termin
