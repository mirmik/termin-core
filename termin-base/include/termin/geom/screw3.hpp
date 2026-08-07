#pragma once

#include "pose3.hpp"
#include "vec3.hpp"
#include "vec6.hpp"
#include <cstddef>
#include <type_traits>

inline tc_screw3 tc_screw3::zero() {
    return {};
}

inline tc_screw3 tc_screw3::operator+(const tc_screw3& s) const {
    return {ang + s.ang, lin + s.lin};
}

inline tc_screw3 tc_screw3::operator-(const tc_screw3& s) const {
    return {ang - s.ang, lin - s.lin};
}

inline tc_screw3 tc_screw3::operator*(double k) const {
    return {ang * k, lin * k};
}

inline tc_screw3 tc_screw3::operator/(double k) const {
    return {ang / k, lin / k};
}

inline tc_screw3 tc_screw3::operator-() const {
    return {-ang, -lin};
}

inline tc_screw3& tc_screw3::operator+=(const tc_screw3& s) {
    ang += s.ang;
    lin += s.lin;
    return *this;
}

inline tc_screw3& tc_screw3::operator-=(const tc_screw3& s) {
    ang -= s.ang;
    lin -= s.lin;
    return *this;
}

inline tc_screw3& tc_screw3::operator*=(double k) {
    ang *= k;
    lin *= k;
    return *this;
}

inline tc_screw3& tc_screw3::operator/=(double k) {
    ang /= k;
    lin /= k;
    return *this;
}

inline tc_screw3 tc_screw3::scaled(double k) const {
    return {ang * k, lin * k};
}

inline double tc_screw3::dot(const tc_screw3& s) const {
    return ang.dot(s.ang) + lin.dot(s.lin);
}

inline tc_screw3 tc_screw3::cross_motion(const tc_screw3& s) const {
    return {ang.cross(s.ang), ang.cross(s.lin) + lin.cross(s.ang)};
}

inline tc_screw3 tc_screw3::cross_force(const tc_screw3& s) const {
    return {ang.cross(s.ang) + lin.cross(s.lin), ang.cross(s.lin)};
}

inline bool tc_screw3::is_finite() const {
    return ang.is_finite() && lin.is_finite();
}

inline tc_screw3 tc_screw3::rotated_by(const tc_quat& orientation) const {
    return {orientation.rotate(ang), orientation.rotate(lin)};
}

inline tc_screw3 tc_screw3::inverse_rotated_by(const tc_quat& orientation) const {
    return {orientation.inverse_rotate(ang), orientation.inverse_rotate(lin)};
}

inline tc_screw3 tc_screw3::adjoint(const tc_pose3& pose) const {
    tc_vec3 ang_world = pose.transform_vector(ang);
    tc_vec3 lin_world = pose.transform_vector(lin) + pose.lin.cross(ang_world);
    return {ang_world, lin_world};
}

inline tc_screw3 tc_screw3::adjoint_inv(const tc_pose3& pose) const {
    tc_vec3 ang_body = pose.inverse_transform_vector(ang);
    tc_vec3 lin_body = pose.inverse_transform_vector(lin - pose.lin.cross(ang));
    return {ang_body, lin_body};
}

inline tc_screw3 tc_screw3::coadjoint(const tc_pose3& pose) const {
    tc_vec3 lin_world = pose.transform_vector(lin);
    tc_vec3 ang_world = pose.transform_vector(ang) + pose.lin.cross(lin_world);
    return {ang_world, lin_world};
}

inline tc_screw3 tc_screw3::coadjoint_inv(const tc_pose3& pose) const {
    tc_vec3 lin_body = pose.inverse_transform_vector(lin);
    tc_vec3 ang_body = pose.inverse_transform_vector(ang - pose.lin.cross(lin));
    return {ang_body, lin_body};
}

inline tc_screw3 tc_screw3::velocity_at_offset(const tc_vec3& offset_from_origin) const {
    return {ang, lin + ang.cross(offset_from_origin)};
}

inline tc_screw3 tc_screw3::velocity_at_origin_from_offset(const tc_vec3& offset_from_origin) const {
    return {ang, lin - ang.cross(offset_from_origin)};
}

inline tc_screw3 tc_screw3::wrench_at_offset(const tc_vec3& offset_from_origin) const {
    return {ang - offset_from_origin.cross(lin), lin};
}

inline tc_screw3 tc_screw3::wrench_at_origin_from_offset(const tc_vec3& offset_from_origin) const {
    return {ang + offset_from_origin.cross(lin), lin};
}

inline tc_screw3 tc_screw3::transform_as_twist_by(const tc_pose3& pose) const {
    return adjoint(pose);
}

inline tc_screw3 tc_screw3::inverse_transform_as_twist_by(const tc_pose3& pose) const {
    return adjoint_inv(pose);
}

inline tc_screw3 tc_screw3::transform_as_wrench_by(const tc_pose3& pose) const {
    return coadjoint(pose);
}

inline tc_screw3 tc_screw3::inverse_transform_as_wrench_by(const tc_pose3& pose) const {
    return coadjoint_inv(pose);
}

inline tc_pose3 tc_screw3::to_pose() const {
    double theta = ang.norm();
    if (theta < 1e-8) {
        return {tc_quat::identity(), lin};
    }

    tc_vec3 axis = ang / theta;
    return {tc_quat::from_axis_angle(axis, theta), lin};
}

namespace termin {

    using Screw3 = ::tc_screw3;

    inline Vec6 screw3_to_vec6_vw(Screw3 value) {
        return {
            value.lin.x,
            value.lin.y,
            value.lin.z,
            value.ang.x,
            value.ang.y,
            value.ang.z,
        };
    }

    inline Screw3 screw3_from_vec6_vw(const Vec6& value) {
        return {
            {value[3], value[4], value[5]},
            {value[0], value[1], value[2]},
        };
    }

    inline Vec6 screw3_to_vec6_wv(Screw3 value) {
        return {
            value.ang.x,
            value.ang.y,
            value.ang.z,
            value.lin.x,
            value.lin.y,
            value.lin.z,
        };
    }

    inline Screw3 screw3_from_vec6_wv(const Vec6& value) {
        return {
            {value[0], value[1], value[2]},
            {value[3], value[4], value[5]},
        };
    }

    static_assert(std::is_same<Screw3, ::tc_screw3>::value, "termin::Screw3 must alias tc_screw3");
    static_assert(std::is_standard_layout<Screw3>::value, "Screw3 must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Screw3>::value, "Screw3 must stay trivially copyable");
    static_assert(sizeof(Screw3) == sizeof(Vec3) * 2, "Screw3 must stay two Vec3 values");
    static_assert(alignof(Screw3) == alignof(Vec3), "Screw3 alignment must match Vec3");
    static_assert(offsetof(Screw3, ang) == 0, "Screw3.ang offset changed");
    static_assert(offsetof(Screw3, lin) == sizeof(Vec3), "Screw3.lin offset changed");

} // namespace termin
