#pragma once

#include "vec3.hpp"
#include <cstddef>
#include <type_traits>

namespace termin {


using Quat = ::tc_quat;

static_assert(std::is_same<Quat, ::tc_quat>::value, "termin::Quat must alias tc_quat");
static_assert(std::is_standard_layout<Quat>::value, "Quat must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Quat>::value, "Quat must stay trivially copyable");
static_assert(sizeof(Quat) == sizeof(double) * 4, "Quat must stay a packed xyzw tuple");
static_assert(alignof(Quat) == alignof(double), "Quat alignment must match double");
static_assert(offsetof(Quat, x) == 0, "Quat.x offset changed");
static_assert(offsetof(Quat, y) == sizeof(double), "Quat.y offset changed");
static_assert(offsetof(Quat, z) == sizeof(double) * 2, "Quat.z offset changed");
static_assert(offsetof(Quat, w) == sizeof(double) * 3, "Quat.w offset changed");

// Spherical linear interpolation
inline Quat slerp(const Quat& q1, Quat q2, double t) {
    return Quat::slerp(q1, q2, t);
}


} // namespace termin
