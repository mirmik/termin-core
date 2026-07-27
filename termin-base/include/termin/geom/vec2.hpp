#pragma once

#include <tcbase/tc_types.h>
#include <cmath>
#include <cstddef>
#include <type_traits>

namespace termin {

using Vec2 = ::tc_vec2;
using Vec2f = ::tc_vec2f;

struct Vec2i {
    int x, y;

    Vec2i() : x(0), y(0) {}
    Vec2i(int x, int y) : x(x), y(y) {}

    int& operator[](int i) { return (&x)[i]; }
    int operator[](int i) const { return (&x)[i]; }

    Vec2i operator+(const Vec2i& v) const { return {x + v.x, y + v.y}; }
    Vec2i operator-(const Vec2i& v) const { return {x - v.x, y - v.y}; }
    Vec2i operator*(int s) const { return {x * s, y * s}; }
    Vec2i operator/(int s) const { return {x / s, y / s}; }
    Vec2i operator-() const { return {-x, -y}; }

    Vec2i& operator+=(const Vec2i& v) { x += v.x; y += v.y; return *this; }
    Vec2i& operator-=(const Vec2i& v) { x -= v.x; y -= v.y; return *this; }
    Vec2i& operator*=(int s) { x *= s; y *= s; return *this; }
    Vec2i& operator/=(int s) { x /= s; y /= s; return *this; }

    bool operator==(const Vec2i& v) const { return x == v.x && y == v.y; }
    bool operator!=(const Vec2i& v) const { return !(*this == v); }

    int dot(const Vec2i& v) const { return x * v.x + y * v.y; }
    int cross(const Vec2i& v) const { return x * v.y - y * v.x; }

    Vec2 to_double() const { return {static_cast<double>(x), static_cast<double>(y)}; }
    Vec2f to_float() const { return {static_cast<float>(x), static_cast<float>(y)}; }

    static Vec2i zero() { return {0, 0}; }
    static Vec2i unit_x() { return {1, 0}; }
    static Vec2i unit_y() { return {0, 1}; }
};

inline Vec2i operator*(int s, const Vec2i& v) { return v * s; }

static_assert(std::is_same<Vec2, ::tc_vec2>::value, "termin::Vec2 must alias tc_vec2");
static_assert(std::is_standard_layout<Vec2>::value, "Vec2 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Vec2>::value, "Vec2 must stay trivially copyable");
static_assert(sizeof(Vec2) == sizeof(double) * 2, "Vec2 must stay a packed xy tuple");
static_assert(alignof(Vec2) == alignof(double), "Vec2 alignment must match double");
static_assert(offsetof(Vec2, x) == 0, "Vec2.x offset changed");
static_assert(offsetof(Vec2, y) == sizeof(double), "Vec2.y offset changed");

static_assert(std::is_same<Vec2f, ::tc_vec2f>::value, "termin::Vec2f must alias tc_vec2f");
static_assert(std::is_standard_layout<Vec2f>::value, "Vec2f must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Vec2f>::value, "Vec2f must stay trivially copyable");
static_assert(sizeof(Vec2f) == sizeof(float) * 2, "Vec2f must stay a packed xy tuple");
static_assert(alignof(Vec2f) == alignof(float), "Vec2f alignment must match float");
static_assert(offsetof(Vec2f, x) == 0, "Vec2f.x offset changed");
static_assert(offsetof(Vec2f, y) == sizeof(float), "Vec2f.y offset changed");

} // namespace termin
