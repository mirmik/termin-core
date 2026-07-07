#pragma once

#include "vec2.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <type_traits>

inline tc_pose2 tc_pose2::identity() {
    return {};
}

inline tc_pose2 tc_pose2::operator*(const tc_pose2& other) const {
    return {ang + other.ang, lin + rotate_vector(other.lin)};
}

inline tc_pose2 tc_pose2::inverse() const {
    tc_pose2 inv{-ang, tc_vec2::zero()};
    return {-ang, inv.rotate_vector(-lin)};
}

inline tc_vec2 tc_pose2::transform_point(const tc_vec2& p) const {
    return rotate_vector(p) + lin;
}

inline tc_vec2 tc_pose2::transform_vector(const tc_vec2& v) const {
    return rotate_vector(v);
}

inline tc_vec2 tc_pose2::rotate_vector(const tc_vec2& v) const {
    double c = std::cos(ang);
    double s = std::sin(ang);
    return {c * v.x - s * v.y, s * v.x + c * v.y};
}

inline tc_vec2 tc_pose2::inverse_transform_point(const tc_vec2& p) const {
    return inverse_rotate_vector(p - lin);
}

inline tc_vec2 tc_pose2::inverse_rotate_vector(const tc_vec2& v) const {
    double c = std::cos(ang);
    double s = std::sin(ang);
    return {c * v.x + s * v.y, -s * v.x + c * v.y};
}

inline tc_vec2 tc_pose2::inverse_transform_vector(const tc_vec2& v) const {
    return inverse_rotate_vector(v);
}

inline tc_pose2 tc_pose2::copy() const {
    return *this;
}

inline void tc_pose2::normalize_angle() {
    ang = std::atan2(std::sin(ang), std::cos(ang));
}

inline tc_pose2 tc_pose2::rotation(double angle) {
    return {angle, tc_vec2::zero()};
}

inline tc_pose2 tc_pose2::translation(double x, double y) {
    return {0.0, {x, y}};
}

inline tc_pose2 tc_pose2::move(double dx, double dy) {
    return translation(dx, dy);
}

inline tc_pose2 tc_pose2::move_x(double distance) {
    return move(distance, 0.0);
}

inline tc_pose2 tc_pose2::move_y(double distance) {
    return move(0.0, distance);
}

inline tc_pose2 tc_pose2::right(double distance) {
    return move(distance, 0.0);
}

inline tc_pose2 tc_pose2::forward(double distance) {
    return move(0.0, distance);
}

inline tc_pose2 tc_pose2::lerp(const tc_pose2& a, const tc_pose2& b, double t) {
    return {
        a.ang + (b.ang - a.ang) * t,
        a.lin + (b.lin - a.lin) * t
    };
}

namespace termin {

using Pose2 = ::tc_pose2;

static_assert(std::is_same<Pose2, ::tc_pose2>::value, "termin::Pose2 must alias tc_pose2");
static_assert(std::is_standard_layout<Pose2>::value, "Pose2 must stay ABI-friendly");
static_assert(std::is_trivially_copyable<Pose2>::value, "Pose2 must stay trivially copyable");
static_assert(offsetof(Pose2, ang) == 0, "Pose2.ang offset changed");
static_assert(offsetof(Pose2, lin) == sizeof(double), "Pose2.lin offset changed");

} // namespace termin
