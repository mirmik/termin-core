#pragma once

#include "pose2.hpp"
#include <cstddef>
#include <type_traits>

namespace termin::detail {

inline tc_vec2 tc_scalar_cross_vec2(double scalar, const tc_vec2& vec) {
    return {scalar * vec.y, -scalar * vec.x};
}

inline tc_vec2 tc_vec2_cross_scalar(const tc_vec2& vec, double scalar) {
    return {-scalar * vec.y, scalar * vec.x};
}

} // namespace termin::detail

inline tc_screw2 tc_screw2::zero() {
    return {};
}

inline tc_screw2 tc_screw2::operator+(const tc_screw2& s) const {
    return {ang + s.ang, lin + s.lin};
}

inline tc_screw2 tc_screw2::operator-(const tc_screw2& s) const {
    return {ang - s.ang, lin - s.lin};
}

inline tc_screw2 tc_screw2::operator*(double k) const {
    return {ang * k, lin * k};
}

inline tc_screw2 tc_screw2::operator/(double k) const {
    return {ang / k, lin / k};
}

inline tc_screw2 tc_screw2::operator-() const {
    return {-ang, -lin};
}

inline tc_screw2& tc_screw2::operator+=(const tc_screw2& s) {
    ang += s.ang;
    lin += s.lin;
    return *this;
}

inline tc_screw2& tc_screw2::operator-=(const tc_screw2& s) {
    ang -= s.ang;
    lin -= s.lin;
    return *this;
}

inline tc_screw2& tc_screw2::operator*=(double k) {
    ang *= k;
    lin *= k;
    return *this;
}

inline tc_screw2& tc_screw2::operator/=(double k) {
    ang /= k;
    lin /= k;
    return *this;
}

inline double tc_screw2::moment() const {
    return ang;
}

inline tc_vec2 tc_screw2::vector() const {
    return lin;
}

inline tc_screw2 tc_screw2::kinematic_carry(const tc_vec2& arm) const {
    return {ang, lin + termin::detail::tc_scalar_cross_vec2(ang, arm)};
}

inline tc_screw2 tc_screw2::force_carry(const tc_vec2& arm) const {
    return {ang - arm.cross(lin), lin};
}

inline tc_screw2 tc_screw2::twist_carry(const tc_vec2& arm) const {
    return kinematic_carry(arm);
}

inline tc_screw2 tc_screw2::wrench_carry(const tc_vec2& arm) const {
    return force_carry(arm);
}

inline tc_screw2 tc_screw2::transform_by(const tc_pose2& pose) const {
    return {ang, pose.transform_vector(lin)};
}

inline tc_screw2 tc_screw2::rotated_by(const tc_pose2& pose) const {
    return transform_by(pose);
}

inline tc_screw2 tc_screw2::inverse_transform_by(const tc_pose2& pose) const {
    return {ang, pose.inverse_transform_vector(lin)};
}

inline tc_screw2 tc_screw2::transform_as_twist_by(const tc_pose2& pose) const {
    tc_vec2 rlin = pose.transform_vector(lin);
    return {ang, rlin + termin::detail::tc_vec2_cross_scalar(pose.lin, ang)};
}

inline tc_screw2 tc_screw2::inverse_transform_as_twist_by(const tc_pose2& pose) const {
    return {ang, pose.inverse_transform_vector(lin - termin::detail::tc_vec2_cross_scalar(pose.lin, ang))};
}

inline tc_screw2 tc_screw2::transform_as_wrench_by(const tc_pose2& pose) const {
    return {ang + pose.lin.cross(lin), pose.transform_vector(lin)};
}

inline tc_screw2 tc_screw2::inverse_transform_as_wrench_by(const tc_pose2& pose) const {
    return {ang - pose.lin.cross(lin), pose.inverse_transform_vector(lin)};
}

inline tc_pose2 tc_screw2::to_pose() const {
    return {ang, lin};
}

inline tc_screw2 tc_screw2::copy() const {
    return *this;
}

inline tc_screw2 tc_screw2::from_vector_vw_order(const double* data) {
    return {data[2], {data[0], data[1]}};
}

inline tc_screw2 tc_screw2::from_vector_wv_order(const double* data) {
    return {data[0], {data[1], data[2]}};
}

namespace termin {

using Screw2 = ::tc_screw2;

static_assert(std::is_same<Screw2, ::tc_screw2>::value, "termin::Screw2 must alias tc_screw2");
static_assert(std::is_standard_layout<Screw2>::value, "Screw2 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Screw2>::value, "Screw2 must stay trivially copyable");
static_assert(offsetof(Screw2, ang) == 0, "Screw2.ang offset changed");
static_assert(offsetof(Screw2, lin) == sizeof(double), "Screw2.lin offset changed");

} // namespace termin
