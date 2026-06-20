#pragma once

#include <cstddef>
#include <tcbase/tc_types.h>
#include <array>
#include <type_traits>

namespace termin {


// ============================================================================
// Vec3 (double)
// ============================================================================

using Vec3 = ::tc_vec3;

static_assert(std::is_same<Vec3, ::tc_vec3>::value, "termin::Vec3 must alias tc_vec3");
static_assert(std::is_standard_layout<Vec3>::value, "Vec3 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Vec3>::value, "Vec3 must stay trivially copyable");
static_assert(sizeof(Vec3) == sizeof(double) * 3, "Vec3 must stay a packed xyz triple");
static_assert(alignof(Vec3) == alignof(double), "Vec3 alignment must match double");
static_assert(offsetof(Vec3, x) == 0, "Vec3.x offset changed");
static_assert(offsetof(Vec3, y) == sizeof(double), "Vec3.y offset changed");
static_assert(offsetof(Vec3, z) == sizeof(double) * 2, "Vec3.z offset changed");


// ============================================================================
// Vec3f (float)
// ============================================================================

using Vec3f = ::tc_vec3f;

static_assert(std::is_same<Vec3f, ::tc_vec3f>::value, "termin::Vec3f must alias tc_vec3f");
static_assert(std::is_standard_layout<Vec3f>::value, "Vec3f must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Vec3f>::value, "Vec3f must stay trivially copyable");
static_assert(sizeof(Vec3f) == sizeof(float) * 3, "Vec3f must stay a packed xyz triple");
static_assert(alignof(Vec3f) == alignof(float), "Vec3f alignment must match float");
static_assert(offsetof(Vec3f, x) == 0, "Vec3f.x offset changed");
static_assert(offsetof(Vec3f, y) == sizeof(float), "Vec3f.y offset changed");
static_assert(offsetof(Vec3f, z) == sizeof(float) * 2, "Vec3f.z offset changed");


// ============================================================================
// Vec3i (int)
// ============================================================================

struct Vec3i {
    int x, y, z;

    Vec3i() : x(0), y(0), z(0) {}
    Vec3i(int x, int y, int z) : x(x), y(y), z(z) {}

    int& operator[](int i) { return (&x)[i]; }
    int operator[](int i) const { return (&x)[i]; }

    Vec3i operator+(const Vec3i& v) const { return {x + v.x, y + v.y, z + v.z}; }
    Vec3i operator-(const Vec3i& v) const { return {x - v.x, y - v.y, z - v.z}; }
    Vec3i operator*(int s) const { return {x * s, y * s, z * s}; }
    Vec3i operator/(int s) const { return {x / s, y / s, z / s}; }
    Vec3i operator-() const { return {-x, -y, -z}; }

    Vec3i& operator+=(const Vec3i& v) { x += v.x; y += v.y; z += v.z; return *this; }
    Vec3i& operator-=(const Vec3i& v) { x -= v.x; y -= v.y; z -= v.z; return *this; }
    Vec3i& operator*=(int s) { x *= s; y *= s; z *= s; return *this; }
    Vec3i& operator/=(int s) { x /= s; y /= s; z /= s; return *this; }

    bool operator==(const Vec3i& v) const { return x == v.x && y == v.y && z == v.z; }
    bool operator!=(const Vec3i& v) const { return !(*this == v); }

    int dot(const Vec3i& v) const { return x * v.x + y * v.y + z * v.z; }

    Vec3i cross(const Vec3i& v) const {
        return {
            y * v.z - z * v.y,
            z * v.x - x * v.z,
            x * v.y - y * v.x
        };
    }

    Vec3 to_double() const { return {static_cast<double>(x), static_cast<double>(y), static_cast<double>(z)}; }
    Vec3f to_float() const { return {static_cast<float>(x), static_cast<float>(y), static_cast<float>(z)}; }

    static Vec3i zero() { return {0, 0, 0}; }
    static Vec3i unit_x() { return {1, 0, 0}; }
    static Vec3i unit_y() { return {0, 1, 0}; }
    static Vec3i unit_z() { return {0, 0, 1}; }
    static Vec3i right() { return unit_x(); }
    static Vec3i left() { return {-1, 0, 0}; }
    static Vec3i forward() { return unit_y(); }
    static Vec3i backward() { return {0, -1, 0}; }
    static Vec3i up() { return unit_z(); }
    static Vec3i down() { return {0, 0, -1}; }
};

inline Vec3i operator*(int s, const Vec3i& v) { return v * s; }


} // namespace termin
