#pragma once

#include <cstddef>
#include <type_traits>

#include <geom/tc_affine3.h>

#include "general_pose3.hpp"
#include "pose3.hpp"
#include "quat.hpp"
#include "vec3.hpp"

inline tc_basis3d tc_basis3d::identity() {
    return tc_basis3d_identity();
}

inline tc_basis3d tc_basis3d::from_quat(const tc_quat& rotation) {
    return tc_basis3d_from_quat(rotation);
}

inline tc_basis3d tc_basis3d::scaling(double sx, double sy, double sz) {
    return tc_basis3d_scaling(sx, sy, sz);
}

inline tc_basis3d tc_basis3d::scaling(const tc_vec3& scale) {
    return scaling(scale.x, scale.y, scale.z);
}

inline tc_basis3d tc_basis3d::scaling(double uniform) {
    return scaling(uniform, uniform, uniform);
}

inline tc_basis3d tc_basis3d::operator*(const tc_basis3d& child) const {
    return tc_basis3d_mul(*this, child);
}

inline tc_vec3 tc_basis3d::transform_vector(const tc_vec3& vector) const {
    return tc_basis3d_transform_vector(*this, vector);
}

inline double tc_basis3d::determinant() const {
    return tc_basis3d_determinant(*this);
}

inline bool tc_basis3d::is_finite() const {
    return tc_basis3d_is_finite(*this);
}

inline bool tc_basis3d::try_inverse(tc_basis3d& out, double epsilon) const {
    return tc_basis3d_try_inverse(*this, epsilon, &out);
}

inline tc_affine3d tc_affine3d::identity() {
    return tc_affine3d_identity();
}

inline tc_affine3d tc_affine3d::from_translation(
    double x,
    double y,
    double z) {
    return tc_affine3d_translation(x, y, z);
}

inline tc_affine3d tc_affine3d::from_translation(const tc_vec3& value) {
    return from_translation(value.x, value.y, value.z);
}

inline tc_affine3d tc_affine3d::from_rotation(const tc_quat& rotation) {
    return tc_affine3d_rotation(rotation);
}

inline tc_affine3d tc_affine3d::scaling(double sx, double sy, double sz) {
    return tc_affine3d_scaling(sx, sy, sz);
}

inline tc_affine3d tc_affine3d::scaling(const tc_vec3& scale) {
    return scaling(scale.x, scale.y, scale.z);
}

inline tc_affine3d tc_affine3d::scaling(double uniform) {
    return scaling(uniform, uniform, uniform);
}

inline tc_affine3d tc_affine3d::trs(
    const tc_vec3& translation,
    const tc_quat& rotation,
    const tc_vec3& scale) {
    return tc_affine3d_trs(translation, rotation, scale);
}

inline tc_affine3d tc_affine3d::from_pose3(const tc_pose3& pose) {
    return tc_affine3d_from_pose3(pose);
}

inline tc_affine3d tc_affine3d::from_general_pose3(
    const tc_general_pose3& pose) {
    return tc_affine3d_from_general_pose3(pose);
}

inline tc_affine3d tc_affine3d::operator*(const tc_affine3d& child) const {
    return tc_affine3d_mul(*this, child);
}

inline tc_vec3 tc_affine3d::transform_point(const tc_vec3& point) const {
    return tc_affine3d_transform_point(*this, point);
}

inline tc_vec3 tc_affine3d::transform_vector(const tc_vec3& vector) const {
    return tc_affine3d_transform_vector(*this, vector);
}

inline double tc_affine3d::determinant() const {
    return tc_affine3d_determinant(*this);
}

inline bool tc_affine3d::is_finite() const {
    return tc_affine3d_is_finite(*this);
}

inline bool tc_affine3d::try_inverse(tc_affine3d& out, double epsilon) const {
    return tc_affine3d_try_inverse(*this, epsilon, &out);
}

inline void tc_affine3d::matrix4(double* out_column_major_16) const {
    tc_affine3d_to_matrix4(*this, out_column_major_16);
}

inline bool tc_affine3d::try_from_matrix4(
    const double* column_major_16,
    tc_affine3d& out,
    double epsilon) {
    return tc_affine3d_try_from_matrix4(
        column_major_16,
        epsilon,
        &out);
}

namespace termin {

using Basis3d = ::tc_basis3d;
using Affine3d = ::tc_affine3d;

static_assert(
    std::is_same<Basis3d, ::tc_basis3d>::value,
    "termin::Basis3d must alias tc_basis3d");
static_assert(
    std::is_standard_layout<Basis3d>::value,
    "Basis3d must stay ABI-friendly");
static_assert(
    std::is_trivially_copyable<Basis3d>::value,
    "Basis3d must stay trivially copyable");
static_assert(
    sizeof(Basis3d) == sizeof(double) * 9,
    "Basis3d must stay a packed nine-double value");
static_assert(offsetof(Basis3d, x) == sizeof(double) * 0, "Basis3d.x offset changed");
static_assert(offsetof(Basis3d, y) == sizeof(double) * 3, "Basis3d.y offset changed");
static_assert(offsetof(Basis3d, z) == sizeof(double) * 6, "Basis3d.z offset changed");

static_assert(
    std::is_same<Affine3d, ::tc_affine3d>::value,
    "termin::Affine3d must alias tc_affine3d");
static_assert(
    std::is_standard_layout<Affine3d>::value,
    "Affine3d must stay ABI-friendly");
static_assert(
    std::is_trivially_copyable<Affine3d>::value,
    "Affine3d must stay trivially copyable");
static_assert(
    sizeof(Affine3d) == sizeof(double) * 12,
    "Affine3d must stay a packed twelve-double value");
static_assert(
    offsetof(Affine3d, basis) == sizeof(double) * 0,
    "Affine3d.basis offset changed");
static_assert(
    offsetof(Affine3d, translation) == sizeof(double) * 9,
    "Affine3d.translation offset changed");

} // namespace termin
