#pragma once

#include "general_pose3.hpp"
#include "pose3.hpp"
#include "vec3.hpp"
#include <algorithm>
#include <cstddef>
#include <type_traits>

inline void tc_aabb::extend(const tc_vec3& point) {
    min_point.x = std::min(min_point.x, point.x);
    min_point.y = std::min(min_point.y, point.y);
    min_point.z = std::min(min_point.z, point.z);
    max_point.x = std::max(max_point.x, point.x);
    max_point.y = std::max(max_point.y, point.y);
    max_point.z = std::max(max_point.z, point.z);
}

inline bool tc_aabb::intersects(const tc_aabb& other) const {
    return max_point.x >= other.min_point.x && other.max_point.x >= min_point.x &&
           max_point.y >= other.min_point.y && other.max_point.y >= min_point.y &&
           max_point.z >= other.min_point.z && other.max_point.z >= min_point.z;
}

inline bool tc_aabb::contains(const tc_vec3& point) const {
    return point.x >= min_point.x && point.x <= max_point.x &&
           point.y >= min_point.y && point.y <= max_point.y &&
           point.z >= min_point.z && point.z <= max_point.z;
}

inline tc_aabb tc_aabb::merge(const tc_aabb& other) const {
    return {
        tc_vec3(
            std::min(min_point.x, other.min_point.x),
            std::min(min_point.y, other.min_point.y),
            std::min(min_point.z, other.min_point.z)),
        tc_vec3(
            std::max(max_point.x, other.max_point.x),
            std::max(max_point.y, other.max_point.y),
            std::max(max_point.z, other.max_point.z))
    };
}

inline tc_vec3 tc_aabb::center() const {
    return (min_point + max_point) * 0.5;
}

inline tc_vec3 tc_aabb::size() const {
    return max_point - min_point;
}

inline tc_vec3 tc_aabb::half_size() const {
    return (max_point - min_point) * 0.5;
}

inline tc_vec3 tc_aabb::project_point(const tc_vec3& point) const {
    return tc_vec3(
        std::clamp(point.x, min_point.x, max_point.x),
        std::clamp(point.y, min_point.y, max_point.y),
        std::clamp(point.z, min_point.z, max_point.z)
    );
}

inline double tc_aabb::surface_area() const {
    tc_vec3 d = max_point - min_point;
    return 2.0 * (d.x * d.y + d.y * d.z + d.z * d.x);
}

inline double tc_aabb::volume() const {
    tc_vec3 d = max_point - min_point;
    return d.x * d.y * d.z;
}

inline tc_aabb tc_aabb::from_points(const tc_vec3* points, size_t count) {
    if (count == 0) {
        return {};
    }
    tc_aabb result(points[0], points[0]);
    for (size_t i = 1; i < count; ++i) {
        result.extend(points[i]);
    }
    return result;
}

inline tc_aabb tc_aabb::transformed_by(const tc_pose3& pose) const {
    tc_vec3 corners[8];
    get_corners(corners);
    tc_vec3 first = pose.transform_point(corners[0]);
    tc_aabb result(first, first);
    for (size_t i = 1; i < 8; ++i) {
        result.extend(pose.transform_point(corners[i]));
    }
    return result;
}

inline tc_aabb tc_aabb::transformed_by(const tc_general_pose3& pose) const {
    tc_vec3 corners[8];
    get_corners(corners);
    tc_vec3 first = pose.transform_point(corners[0]);
    tc_aabb result(first, first);
    for (size_t i = 1; i < 8; ++i) {
        result.extend(pose.transform_point(corners[i]));
    }
    return result;
}

inline void tc_aabb::get_corners(tc_vec3* out_corners) const {
    out_corners[0] = {min_point.x, min_point.y, min_point.z};
    out_corners[1] = {min_point.x, min_point.y, max_point.z};
    out_corners[2] = {min_point.x, max_point.y, min_point.z};
    out_corners[3] = {min_point.x, max_point.y, max_point.z};
    out_corners[4] = {max_point.x, min_point.y, min_point.z};
    out_corners[5] = {max_point.x, min_point.y, max_point.z};
    out_corners[6] = {max_point.x, max_point.y, min_point.z};
    out_corners[7] = {max_point.x, max_point.y, max_point.z};
}

namespace termin {

using AABB = ::tc_aabb;

static_assert(std::is_same<AABB, ::tc_aabb>::value, "termin::AABB must alias tc_aabb");
static_assert(std::is_standard_layout<AABB>::value, "AABB must stay ABI-friendly");
static_assert(std::is_trivially_copyable<AABB>::value, "AABB must stay trivially copyable");
static_assert(sizeof(AABB) == sizeof(Vec3) * 2, "AABB must stay two Vec3 values");
static_assert(alignof(AABB) == alignof(Vec3), "AABB alignment must match Vec3");
static_assert(offsetof(AABB, min_point) == 0, "AABB.min_point offset changed");
static_assert(offsetof(AABB, max_point) == sizeof(Vec3), "AABB.max_point offset changed");

} // namespace termin
