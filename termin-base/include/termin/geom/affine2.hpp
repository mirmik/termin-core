#pragma once

#include <cstddef>
#include <type_traits>

#include <geom/tc_affine2.h>

#include "bounds2.hpp"
#include "pose2.hpp"
#include "vec2.hpp"

inline tc_affine2f::tc_affine2f(const tc_pose2& pose) noexcept
    : tc_affine2f(tc_affine2f_from_pose2(pose)) {}

inline tc_affine2f tc_affine2f::identity() {
    return tc_affine2f_identity();
}

inline tc_affine2f tc_affine2f::translation(float x, float y) {
    return tc_affine2f_translation(x, y);
}

inline tc_affine2f tc_affine2f::translation(const tc_vec2f& value) {
    return translation(value.x, value.y);
}

inline tc_affine2f tc_affine2f::rotation(float radians) {
    return tc_affine2f_rotation(radians);
}

inline tc_affine2f tc_affine2f::scaling(float sx, float sy) {
    return tc_affine2f_scaling(sx, sy);
}

inline tc_affine2f tc_affine2f::scaling(const tc_vec2f& value) {
    return scaling(value.x, value.y);
}

inline tc_affine2f tc_affine2f::scaling(float uniform) {
    return scaling(uniform, uniform);
}

inline tc_affine2f tc_affine2f::shear(float x_by_y, float y_by_x) {
    return tc_affine2f_shear(x_by_y, y_by_x);
}

inline tc_affine2f tc_affine2f::trs(const tc_vec2f& translation, float radians, const tc_vec2f& scale) {
    return tc_affine2f_trs(translation, radians, scale);
}

inline tc_affine2f tc_affine2f::from_pose2(const tc_pose2& pose) {
    return tc_affine2f_from_pose2(pose);
}

inline tc_affine2f tc_affine2f::operator*(const tc_affine2f& child) const {
    return tc_affine2f_mul(*this, child);
}

inline tc_vec2f tc_affine2f::transform_point(const tc_vec2f& point) const {
    return tc_affine2f_transform_point(*this, point);
}

inline tc_vec2f tc_affine2f::transform_vector(const tc_vec2f& vector) const {
    return tc_affine2f_transform_vector(*this, vector);
}

inline tc_bounds2f tc_affine2f::transform_bounds(const tc_bounds2f& bounds) const {
    return tc_affine2f_transform_bounds(*this, bounds);
}

inline float tc_affine2f::determinant() const {
    return tc_affine2f_determinant(*this);
}

inline bool tc_affine2f::is_finite() const {
    return tc_affine2f_is_finite(*this);
}

inline bool tc_affine2f::try_inverse(tc_affine2f& out, float epsilon) const {
    return tc_affine2f_try_inverse(*this, epsilon, &out);
}

namespace termin {

    using Affine2f = ::tc_affine2f;

    static_assert(std::is_same<Affine2f, ::tc_affine2f>::value, "termin::Affine2f must alias tc_affine2f");
    static_assert(std::is_standard_layout<Affine2f>::value, "Affine2f must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Affine2f>::value, "Affine2f must stay trivially copyable");
    static_assert(sizeof(Affine2f) == sizeof(float) * 6, "Affine2f must stay a packed six-float value");
    static_assert(offsetof(Affine2f, m00) == sizeof(float) * 0, "Affine2f.m00 offset changed");
    static_assert(offsetof(Affine2f, m01) == sizeof(float) * 1, "Affine2f.m01 offset changed");
    static_assert(offsetof(Affine2f, m10) == sizeof(float) * 2, "Affine2f.m10 offset changed");
    static_assert(offsetof(Affine2f, m11) == sizeof(float) * 3, "Affine2f.m11 offset changed");
    static_assert(offsetof(Affine2f, tx) == sizeof(float) * 4, "Affine2f.tx offset changed");
    static_assert(offsetof(Affine2f, ty) == sizeof(float) * 5, "Affine2f.ty offset changed");

} // namespace termin
