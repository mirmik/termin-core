#pragma once

#include <cmath>
#include <cstddef>
#include <type_traits>
#include "vec3.hpp"
#include "quat.hpp"
#include "pose3.hpp"

inline tc_general_pose3 tc_general_pose3::identity() {
    return {};
}

inline tc_general_pose3 tc_general_pose3::operator*(const tc_general_pose3& other) const {
    tc_vec3 scaled_child{scale.x * other.lin.x, scale.y * other.lin.y, scale.z * other.lin.z};
    tc_vec3 rotated_child = ang.rotate(scaled_child);
    return {
        ang * other.ang,
        lin + rotated_child,
        {scale.x * other.scale.x, scale.y * other.scale.y, scale.z * other.scale.z}
    };
}

inline tc_general_pose3 tc_general_pose3::operator*(const tc_pose3& other) const {
    tc_vec3 scaled_child{scale.x * other.lin.x, scale.y * other.lin.y, scale.z * other.lin.z};
    tc_vec3 rotated_child = ang.rotate(scaled_child);
    return {
        ang * other.ang,
        lin + rotated_child,
        scale
    };
}

inline tc_general_pose3 tc_general_pose3::inverse() const {
    tc_quat inv_ang = ang.inverse();
    tc_vec3 inv_scale{
        scale.x != 0.0 ? 1.0 / scale.x : 0.0,
        scale.y != 0.0 ? 1.0 / scale.y : 0.0,
        scale.z != 0.0 ? 1.0 / scale.z : 0.0
    };
    tc_vec3 inv_lin = inv_ang.rotate(-lin);
    inv_lin.x *= inv_scale.x;
    inv_lin.y *= inv_scale.y;
    inv_lin.z *= inv_scale.z;
    return {inv_ang, inv_lin, inv_scale};
}

inline tc_vec3 tc_general_pose3::transform_point(const tc_vec3& p) const {
    tc_vec3 scaled{scale.x * p.x, scale.y * p.y, scale.z * p.z};
    return ang.rotate(scaled) + lin;
}

inline tc_vec3 tc_general_pose3::transform_vector(const tc_vec3& v) const {
    tc_vec3 scaled{scale.x * v.x, scale.y * v.y, scale.z * v.z};
    return ang.rotate(scaled);
}

inline tc_vec3 tc_general_pose3::transform_direction(const tc_vec3& d) const {
    return ang.rotate(d);
}

inline tc_vec3 tc_general_pose3::rotate_point(const tc_vec3& p) const {
    return transform_vector(p);
}

inline tc_vec3 tc_general_pose3::inverse_transform_point(const tc_vec3& p) const {
    tc_vec3 inv_scale{
        scale.x != 0.0 ? 1.0 / scale.x : 0.0,
        scale.y != 0.0 ? 1.0 / scale.y : 0.0,
        scale.z != 0.0 ? 1.0 / scale.z : 0.0
    };
    tc_vec3 diff = p - lin;
    tc_vec3 rot = ang.inverse_rotate(diff);
    rot.x *= inv_scale.x;
    rot.y *= inv_scale.y;
    rot.z *= inv_scale.z;
    return rot;
}

inline tc_vec3 tc_general_pose3::inverse_transform_vector(const tc_vec3& v) const {
    tc_vec3 inv_scale{
        scale.x != 0.0 ? 1.0 / scale.x : 0.0,
        scale.y != 0.0 ? 1.0 / scale.y : 0.0,
        scale.z != 0.0 ? 1.0 / scale.z : 0.0
    };
    tc_vec3 rot = ang.inverse_rotate(v);
    rot.x *= inv_scale.x;
    rot.y *= inv_scale.y;
    rot.z *= inv_scale.z;
    return rot;
}

inline tc_vec3 tc_general_pose3::inverse_transform_direction(const tc_vec3& d) const {
    return ang.inverse_rotate(d);
}

inline tc_vec3 tc_general_pose3::point_to_global(const tc_vec3& p) const {
    return transform_point(p);
}

inline tc_vec3 tc_general_pose3::vector_to_global(const tc_vec3& v) const {
    return transform_vector(v);
}

inline tc_vec3 tc_general_pose3::direction_to_global(const tc_vec3& d) const {
    return transform_direction(d);
}

inline tc_vec3 tc_general_pose3::point_to_local(const tc_vec3& p) const {
    return inverse_transform_point(p);
}

inline tc_vec3 tc_general_pose3::vector_to_local(const tc_vec3& v) const {
    return inverse_transform_vector(v);
}

inline tc_vec3 tc_general_pose3::direction_to_local(const tc_vec3& d) const {
    return inverse_transform_direction(d);
}

inline tc_vec3 tc_general_pose3::forward_in_global(double distance) const {
    return transform_direction(tc_vec3{0.0, distance, 0.0});
}

inline tc_vec3 tc_general_pose3::backward_in_global(double distance) const {
    return transform_direction(tc_vec3{0.0, -distance, 0.0});
}

inline tc_vec3 tc_general_pose3::up_in_global(double distance) const {
    return transform_direction(tc_vec3{0.0, 0.0, distance});
}

inline tc_vec3 tc_general_pose3::down_in_global(double distance) const {
    return transform_direction(tc_vec3{0.0, 0.0, -distance});
}

inline tc_vec3 tc_general_pose3::right_in_global(double distance) const {
    return transform_direction(tc_vec3{distance, 0.0, 0.0});
}

inline tc_vec3 tc_general_pose3::left_in_global(double distance) const {
    return transform_direction(tc_vec3{-distance, 0.0, 0.0});
}

inline tc_vec3 tc_general_pose3::global_forward_in_local(double distance) const {
    return inverse_transform_direction(tc_vec3{0.0, distance, 0.0});
}

inline tc_vec3 tc_general_pose3::global_backward_in_local(double distance) const {
    return inverse_transform_direction(tc_vec3{0.0, -distance, 0.0});
}

inline tc_vec3 tc_general_pose3::global_up_in_local(double distance) const {
    return inverse_transform_direction(tc_vec3{0.0, 0.0, distance});
}

inline tc_vec3 tc_general_pose3::global_down_in_local(double distance) const {
    return inverse_transform_direction(tc_vec3{0.0, 0.0, -distance});
}

inline tc_vec3 tc_general_pose3::global_right_in_local(double distance) const {
    return inverse_transform_direction(tc_vec3{distance, 0.0, 0.0});
}

inline tc_vec3 tc_general_pose3::global_left_in_local(double distance) const {
    return inverse_transform_direction(tc_vec3{-distance, 0.0, 0.0});
}

inline tc_general_pose3 tc_general_pose3::normalized() const {
    return {ang.normalized(), lin, scale};
}

inline tc_general_pose3 tc_general_pose3::with_rotation(const tc_quat& new_ang) const {
    return {new_ang, lin, scale};
}

inline tc_general_pose3 tc_general_pose3::with_translation(const tc_vec3& new_lin) const {
    return {ang, new_lin, scale};
}

inline tc_general_pose3 tc_general_pose3::with_scale(const tc_vec3& new_scale) const {
    return {ang, lin, new_scale};
}

inline tc_pose3 tc_general_pose3::to_pose3() const {
    return {ang, lin};
}

inline void tc_general_pose3::rotation_matrix(double* m) const {
    ang.to_matrix(m);
}

inline void tc_general_pose3::matrix4(double* m) const {
    double r[9];
    rotation_matrix(r);
    m[0] = r[0] * scale.x; m[1] = r[3] * scale.x; m[2] = r[6] * scale.x; m[3] = 0.0;
    m[4] = r[1] * scale.y; m[5] = r[4] * scale.y; m[6] = r[7] * scale.y; m[7] = 0.0;
    m[8] = r[2] * scale.z; m[9] = r[5] * scale.z; m[10] = r[8] * scale.z; m[11] = 0.0;
    m[12] = lin.x; m[13] = lin.y; m[14] = lin.z; m[15] = 1.0;
}

inline void tc_general_pose3::matrix34(double* m) const {
    double r[9];
    rotation_matrix(r);
    m[0] = r[0] * scale.x; m[1] = r[3] * scale.x; m[2] = r[6] * scale.x;
    m[3] = r[1] * scale.y; m[4] = r[4] * scale.y; m[5] = r[7] * scale.y;
    m[6] = r[2] * scale.z; m[7] = r[5] * scale.z; m[8] = r[8] * scale.z;
    m[9] = lin.x; m[10] = lin.y; m[11] = lin.z;
}

inline void tc_general_pose3::inverse_matrix4(double* m) const {
    double r[9];
    rotation_matrix(r);

    double inv_sx = scale.x != 0.0 ? 1.0 / scale.x : 0.0;
    double inv_sy = scale.y != 0.0 ? 1.0 / scale.y : 0.0;
    double inv_sz = scale.z != 0.0 ? 1.0 / scale.z : 0.0;

    double m00 = inv_sx * r[0];
    double m01 = inv_sx * r[3];
    double m02 = inv_sx * r[6];

    double m10 = inv_sy * r[1];
    double m11 = inv_sy * r[4];
    double m12 = inv_sy * r[7];

    double m20 = inv_sz * r[2];
    double m21 = inv_sz * r[5];
    double m22 = inv_sz * r[8];

    double tx = -(m00 * lin.x + m01 * lin.y + m02 * lin.z);
    double ty = -(m10 * lin.x + m11 * lin.y + m12 * lin.z);
    double tz = -(m20 * lin.x + m21 * lin.y + m22 * lin.z);

    m[0] = m00; m[1] = m10; m[2] = m20; m[3] = 0.0;
    m[4] = m01; m[5] = m11; m[6] = m21; m[7] = 0.0;
    m[8] = m02; m[9] = m12; m[10] = m22; m[11] = 0.0;
    m[12] = tx; m[13] = ty; m[14] = tz; m[15] = 1.0;
}

inline double tc_general_pose3::distance(const tc_general_pose3& other) const {
    return (lin - other.lin).norm();
}

inline tc_general_pose3 tc_general_pose3::translation(double x, double y, double z) {
    return {tc_quat::identity(), {x, y, z}, {1.0, 1.0, 1.0}};
}

inline tc_general_pose3 tc_general_pose3::translation(const tc_vec3& t) {
    return {tc_quat::identity(), t, {1.0, 1.0, 1.0}};
}

inline tc_general_pose3 tc_general_pose3::rotation(const tc_vec3& axis, double angle) {
    return {tc_quat::from_axis_angle(axis, angle), tc_vec3::zero(), {1.0, 1.0, 1.0}};
}

inline tc_general_pose3 tc_general_pose3::scaling(double sx, double sy, double sz) {
    return {tc_quat::identity(), tc_vec3::zero(), {sx, sy, sz}};
}

inline tc_general_pose3 tc_general_pose3::scaling(double s) {
    return {tc_quat::identity(), tc_vec3::zero(), {s, s, s}};
}

inline tc_general_pose3 tc_general_pose3::rotate_x(double angle) {
    return rotation(tc_vec3::unit_x(), angle);
}

inline tc_general_pose3 tc_general_pose3::rotate_y(double angle) {
    return rotation(tc_vec3::unit_y(), angle);
}

inline tc_general_pose3 tc_general_pose3::rotate_z(double angle) {
    return rotation(tc_vec3::unit_z(), angle);
}

inline tc_general_pose3 tc_general_pose3::move(double dx, double dy, double dz) {
    return translation(dx, dy, dz);
}

inline tc_general_pose3 tc_general_pose3::move_x(double d) {
    return move(d, 0.0, 0.0);
}

inline tc_general_pose3 tc_general_pose3::move_y(double d) {
    return move(0.0, d, 0.0);
}

inline tc_general_pose3 tc_general_pose3::move_z(double d) {
    return move(0.0, 0.0, d);
}

inline tc_general_pose3 tc_general_pose3::right(double d) {
    return move_x(d);
}

inline tc_general_pose3 tc_general_pose3::forward(double d) {
    return move_y(d);
}

inline tc_general_pose3 tc_general_pose3::up(double d) {
    return move_z(d);
}

inline tc_general_pose3 tc_general_pose3::looking_at(
    const tc_vec3& eye,
    const tc_vec3& target,
    const tc_vec3& up_vec) {
    tc_vec3 forward_vec = (target - eye).normalized();
    tc_vec3 right_vec = forward_vec.cross(up_vec).normalized();
    tc_vec3 up_corrected = right_vec.cross(forward_vec);

    double r00 = right_vec.x,   r01 = forward_vec.x,   r02 = up_corrected.x;
    double r10 = right_vec.y,   r11 = forward_vec.y,   r12 = up_corrected.y;
    double r20 = right_vec.z,   r21 = forward_vec.z,   r22 = up_corrected.z;

    double trace = r00 + r11 + r22;
    tc_quat q;
    if (trace > 0.0) {
        double s = 0.5 / std::sqrt(trace + 1.0);
        q.w = 0.25 / s;
        q.x = (r21 - r12) * s;
        q.y = (r02 - r20) * s;
        q.z = (r10 - r01) * s;
    } else if (r00 > r11 && r00 > r22) {
        double s = 2.0 * std::sqrt(1.0 + r00 - r11 - r22);
        q.w = (r21 - r12) / s;
        q.x = 0.25 * s;
        q.y = (r01 + r10) / s;
        q.z = (r02 + r20) / s;
    } else if (r11 > r22) {
        double s = 2.0 * std::sqrt(1.0 + r11 - r00 - r22);
        q.w = (r02 - r20) / s;
        q.x = (r01 + r10) / s;
        q.y = 0.25 * s;
        q.z = (r12 + r21) / s;
    } else {
        double s = 2.0 * std::sqrt(1.0 + r22 - r00 - r11);
        q.w = (r10 - r01) / s;
        q.x = (r02 + r20) / s;
        q.y = (r12 + r21) / s;
        q.z = 0.25 * s;
    }

    return {q, eye, {1.0, 1.0, 1.0}};
}

namespace termin {

using GeneralPose3 = ::tc_general_pose3;

static_assert(std::is_same<GeneralPose3, ::tc_general_pose3>::value,
              "termin::GeneralPose3 must alias tc_general_pose3");
static_assert(std::is_standard_layout<GeneralPose3>::value,
              "GeneralPose3 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<GeneralPose3>::value,
              "GeneralPose3 must stay trivially copyable");
static_assert(offsetof(GeneralPose3, ang) == 0, "GeneralPose3.ang offset changed");
static_assert(offsetof(GeneralPose3, lin) == sizeof(Quat),
              "GeneralPose3.lin offset changed");
static_assert(offsetof(GeneralPose3, scale) == sizeof(Quat) + sizeof(Vec3),
              "GeneralPose3.scale offset changed");

inline GeneralPose3 lerp(const GeneralPose3& a, const GeneralPose3& b, double t) {
    return {
        slerp(a.ang, b.ang, t),
        a.lin + (b.lin - a.lin) * t,
        {a.scale.x + (b.scale.x - a.scale.x) * t,
         a.scale.y + (b.scale.y - a.scale.y) * t,
         a.scale.z + (b.scale.z - a.scale.z) * t}
    };
}

inline GeneralPose3 operator*(const Pose3& a, const GeneralPose3& b) {
    Vec3 rotated_child = a.ang.rotate(b.lin);
    return {
        a.ang * b.ang,
        a.lin + rotated_child,
        b.scale
    };
}

} // namespace termin
