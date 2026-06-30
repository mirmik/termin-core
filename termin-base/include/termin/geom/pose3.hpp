#pragma once

#include "vec3.hpp"
#include "quat.hpp"
#include "mat44.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <type_traits>

inline tc_pose3 tc_pose3::identity() {
    return {};
}

inline tc_pose3 tc_pose3::operator*(const tc_pose3& other) const {
    return {
        ang * other.ang,
        lin + ang.rotate(other.lin)
    };
}

inline tc_pose3 tc_pose3::inverse() const {
    tc_quat inv_ang = ang.inverse();
    return {inv_ang, inv_ang.rotate(-lin)};
}

inline tc_vec3 tc_pose3::transform_point(const tc_vec3& p) const {
    return ang.rotate(p) + lin;
}

inline tc_vec3 tc_pose3::transform_vector(const tc_vec3& v) const {
    return ang.rotate(v);
}

inline tc_vec3 tc_pose3::rotate_point(const tc_vec3& p) const {
    return transform_vector(p);
}

inline tc_vec3 tc_pose3::inverse_transform_point(const tc_vec3& p) const {
    return ang.inverse_rotate(p - lin);
}

inline tc_vec3 tc_pose3::inverse_transform_vector(const tc_vec3& v) const {
    return ang.inverse_rotate(v);
}

inline tc_vec3 tc_pose3::point_to_global(const tc_vec3& p) const {
    return transform_point(p);
}

inline tc_vec3 tc_pose3::vector_to_global(const tc_vec3& v) const {
    return transform_vector(v);
}

inline tc_vec3 tc_pose3::point_to_local(const tc_vec3& p) const {
    return inverse_transform_point(p);
}

inline tc_vec3 tc_pose3::vector_to_local(const tc_vec3& v) const {
    return inverse_transform_vector(v);
}

inline tc_vec3 tc_pose3::forward_in_global(double distance) const {
    return transform_vector(tc_vec3{0.0, distance, 0.0});
}

inline tc_vec3 tc_pose3::backward_in_global(double distance) const {
    return transform_vector(tc_vec3{0.0, -distance, 0.0});
}

inline tc_vec3 tc_pose3::up_in_global(double distance) const {
    return transform_vector(tc_vec3{0.0, 0.0, distance});
}

inline tc_vec3 tc_pose3::down_in_global(double distance) const {
    return transform_vector(tc_vec3{0.0, 0.0, -distance});
}

inline tc_vec3 tc_pose3::right_in_global(double distance) const {
    return transform_vector(tc_vec3{distance, 0.0, 0.0});
}

inline tc_vec3 tc_pose3::left_in_global(double distance) const {
    return transform_vector(tc_vec3{-distance, 0.0, 0.0});
}

inline tc_vec3 tc_pose3::global_forward_in_local(double distance) const {
    return inverse_transform_vector(tc_vec3{0.0, distance, 0.0});
}

inline tc_vec3 tc_pose3::global_backward_in_local(double distance) const {
    return inverse_transform_vector(tc_vec3{0.0, -distance, 0.0});
}

inline tc_vec3 tc_pose3::global_up_in_local(double distance) const {
    return inverse_transform_vector(tc_vec3{0.0, 0.0, distance});
}

inline tc_vec3 tc_pose3::global_down_in_local(double distance) const {
    return inverse_transform_vector(tc_vec3{0.0, 0.0, -distance});
}

inline tc_vec3 tc_pose3::global_right_in_local(double distance) const {
    return inverse_transform_vector(tc_vec3{distance, 0.0, 0.0});
}

inline tc_vec3 tc_pose3::global_left_in_local(double distance) const {
    return inverse_transform_vector(tc_vec3{-distance, 0.0, 0.0});
}

inline tc_pose3 tc_pose3::normalized() const {
    return {ang.normalized(), lin};
}

inline tc_pose3 tc_pose3::with_translation(const tc_vec3& new_lin) const {
    return {ang, new_lin};
}

inline tc_pose3 tc_pose3::with_rotation(const tc_quat& new_ang) const {
    return {new_ang, lin};
}

inline void tc_pose3::rotation_matrix(double* m) const {
    ang.to_matrix(m);
}

inline void tc_pose3::as_matrix(double* m) const {
    double rot[9];
    ang.to_matrix(rot);
    m[0] = rot[0]; m[1] = rot[3]; m[2] = rot[6]; m[3] = 0;
    m[4] = rot[1]; m[5] = rot[4]; m[6] = rot[7]; m[7] = 0;
    m[8] = rot[2]; m[9] = rot[5]; m[10] = rot[8]; m[11] = 0;
    m[12] = lin.x; m[13] = lin.y; m[14] = lin.z; m[15] = 1;
}

inline termin::Mat44 tc_pose3::as_mat44() const {
    termin::Mat44 m;
    as_matrix(m.data);
    return m;
}

inline double tc_pose3::distance(const tc_pose3& other) const {
    return (lin - other.lin).norm();
}

inline tc_pose3 tc_pose3::translation(double x, double y, double z) {
    return {tc_quat::identity(), {x, y, z}};
}

inline tc_pose3 tc_pose3::translation(const tc_vec3& t) {
    return {tc_quat::identity(), t};
}

inline tc_pose3 tc_pose3::rotation(const tc_vec3& axis, double angle) {
    return {tc_quat::from_axis_angle(axis, angle), tc_vec3::zero()};
}

inline tc_pose3 tc_pose3::rotate_x(double angle) {
    return rotation(tc_vec3::unit_x(), angle);
}

inline tc_pose3 tc_pose3::rotate_y(double angle) {
    return rotation(tc_vec3::unit_y(), angle);
}

inline tc_pose3 tc_pose3::rotate_z(double angle) {
    return rotation(tc_vec3::unit_z(), angle);
}

inline tc_pose3 tc_pose3::looking_at(
    const tc_vec3& eye,
    const tc_vec3& target,
    const tc_vec3& up) {
    tc_vec3 forward = (target - eye).normalized();
    tc_vec3 right = forward.cross(up).normalized();
    tc_vec3 up_corrected = right.cross(forward);

    double m00 = right.x, m01 = forward.x, m02 = up_corrected.x;
    double m10 = right.y, m11 = forward.y, m12 = up_corrected.y;
    double m20 = right.z, m21 = forward.z, m22 = up_corrected.z;

    double trace = m00 + m11 + m22;
    tc_quat q;

    if (trace > 0) {
        double s = 0.5 / std::sqrt(trace + 1.0);
        q = tc_quat(
            (m21 - m12) * s,
            (m02 - m20) * s,
            (m10 - m01) * s,
            0.25 / s
        );
    } else if (m00 > m11 && m00 > m22) {
        double s = 2.0 * std::sqrt(1.0 + m00 - m11 - m22);
        q = tc_quat(
            0.25 * s,
            (m01 + m10) / s,
            (m02 + m20) / s,
            (m21 - m12) / s
        );
    } else if (m11 > m22) {
        double s = 2.0 * std::sqrt(1.0 + m11 - m00 - m22);
        q = tc_quat(
            (m01 + m10) / s,
            0.25 * s,
            (m12 + m21) / s,
            (m02 - m20) / s
        );
    } else {
        double s = 2.0 * std::sqrt(1.0 + m22 - m00 - m11);
        q = tc_quat(
            (m02 + m20) / s,
            (m12 + m21) / s,
            0.25 * s,
            (m10 - m01) / s
        );
    }

    return {q.normalized(), eye};
}

inline tc_pose3 tc_pose3::from_euler(double roll, double pitch, double yaw) {
    double cr = std::cos(roll * 0.5);
    double sr = std::sin(roll * 0.5);
    double cp = std::cos(pitch * 0.5);
    double sp = std::sin(pitch * 0.5);
    double cy = std::cos(yaw * 0.5);
    double sy = std::sin(yaw * 0.5);

    tc_quat q(
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy
    );
    return {q, tc_vec3::zero()};
}

inline tc_vec3 tc_pose3::to_euler() const {
    double x = ang.x, y = ang.y, z = ang.z, w = ang.w;

    double sinr_cosp = 2 * (w * x + y * z);
    double cosr_cosp = 1 - 2 * (x * x + y * y);
    double roll = std::atan2(sinr_cosp, cosr_cosp);

    double sinp = 2 * (w * y - z * x);
    sinp = std::clamp(sinp, -1.0, 1.0);
    double pitch = std::asin(sinp);

    double siny_cosp = 2 * (w * z + x * y);
    double cosy_cosp = 1 - 2 * (y * y + z * z);
    double yaw = std::atan2(siny_cosp, cosy_cosp);

    return {roll, pitch, yaw};
}

inline void tc_pose3::to_axis_angle(tc_vec3& axis, double& angle) const {
    angle = 2 * std::acos(std::clamp(ang.w, -1.0, 1.0));
    double s = std::sqrt(1 - ang.w * ang.w);
    if (s < 0.001) {
        axis = tc_vec3::unit_x();
    } else {
        axis = tc_vec3(ang.x / s, ang.y / s, ang.z / s);
    }
}

inline tc_pose3 tc_pose3::copy() const {
    return *this;
}

namespace termin {

using Pose3 = ::tc_pose3;

static_assert(std::is_same<Pose3, ::tc_pose3>::value, "termin::Pose3 must alias tc_pose3");
static_assert(std::is_standard_layout<Pose3>::value, "Pose3 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Pose3>::value, "Pose3 must stay trivially copyable");
static_assert(offsetof(Pose3, ang) == 0, "Pose3.ang offset changed");
static_assert(offsetof(Pose3, lin) == sizeof(Quat), "Pose3.lin offset changed");

inline Pose3 lerp(const Pose3& p1, const Pose3& p2, double t) {
    return {
        slerp(p1.ang, p2.ang, t),
        p1.lin + (p2.lin - p1.lin) * t
    };
}

} // namespace termin
