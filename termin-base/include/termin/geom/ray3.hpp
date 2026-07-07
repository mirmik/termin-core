#pragma once

#include "vec3.hpp"
#include <cstddef>
#include <type_traits>

namespace termin {


using Ray3 = ::tc_ray3;

static_assert(std::is_same<Ray3, ::tc_ray3>::value, "termin::Ray3 must alias tc_ray3");
static_assert(std::is_standard_layout<Ray3>::value, "Ray3 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Ray3>::value, "Ray3 must stay trivially copyable");
static_assert(sizeof(Ray3) == sizeof(Vec3) * 2, "Ray3 must stay a packed origin/direction pair");
static_assert(alignof(Ray3) == alignof(Vec3), "Ray3 alignment must match Vec3");
static_assert(offsetof(Ray3, origin) == 0, "Ray3.origin offset changed");
static_assert(offsetof(Ray3, direction) == sizeof(Vec3), "Ray3.direction offset changed");


} // namespace termin
