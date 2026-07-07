// tc_aabb.h - Axis-aligned bounding boxes
#ifndef TC_AABB_H
#define TC_AABB_H

#include <tcbase/tc_types.h>
#include "geom/tc_pose.h"
#include "geom/tc_vec3.h"
#include <math.h>

#ifdef __cplusplus
    #define TC_AABB(min_, max_) tc_aabb{min_, max_}
#else
    #define TC_AABB(min_, max_) (tc_aabb){min_, max_}
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline tc_aabb tc_aabb_new(tc_vec3 min_point, tc_vec3 max_point) {
    return TC_AABB(min_point, max_point);
}

static inline tc_aabb tc_aabb_zero(void) {
    return TC_AABB(tc_vec3_zero(), tc_vec3_zero());
}

static inline void tc_aabb_extend(tc_aabb* box, tc_vec3 point) {
    box->min_point.x = fmin(box->min_point.x, point.x);
    box->min_point.y = fmin(box->min_point.y, point.y);
    box->min_point.z = fmin(box->min_point.z, point.z);
    box->max_point.x = fmax(box->max_point.x, point.x);
    box->max_point.y = fmax(box->max_point.y, point.y);
    box->max_point.z = fmax(box->max_point.z, point.z);
}

static inline bool tc_aabb_intersects(tc_aabb a, tc_aabb b) {
    return a.max_point.x >= b.min_point.x && b.max_point.x >= a.min_point.x &&
           a.max_point.y >= b.min_point.y && b.max_point.y >= a.min_point.y &&
           a.max_point.z >= b.min_point.z && b.max_point.z >= a.min_point.z;
}

static inline bool tc_aabb_contains(tc_aabb box, tc_vec3 point) {
    return point.x >= box.min_point.x && point.x <= box.max_point.x &&
           point.y >= box.min_point.y && point.y <= box.max_point.y &&
           point.z >= box.min_point.z && point.z <= box.max_point.z;
}

static inline tc_aabb tc_aabb_merge(tc_aabb a, tc_aabb b) {
    return TC_AABB(
        TC_VEC3(
            fmin(a.min_point.x, b.min_point.x),
            fmin(a.min_point.y, b.min_point.y),
            fmin(a.min_point.z, b.min_point.z)
        ),
        TC_VEC3(
            fmax(a.max_point.x, b.max_point.x),
            fmax(a.max_point.y, b.max_point.y),
            fmax(a.max_point.z, b.max_point.z)
        )
    );
}

static inline tc_vec3 tc_aabb_center(tc_aabb box) {
    return tc_vec3_scale(tc_vec3_add(box.min_point, box.max_point), 0.5);
}

static inline tc_vec3 tc_aabb_size(tc_aabb box) {
    return tc_vec3_sub(box.max_point, box.min_point);
}

static inline tc_vec3 tc_aabb_half_size(tc_aabb box) {
    return tc_vec3_scale(tc_aabb_size(box), 0.5);
}

static inline tc_vec3 tc_aabb_project_point(tc_aabb box, tc_vec3 point) {
    return TC_VEC3(
        fmin(fmax(point.x, box.min_point.x), box.max_point.x),
        fmin(fmax(point.y, box.min_point.y), box.max_point.y),
        fmin(fmax(point.z, box.min_point.z), box.max_point.z)
    );
}

static inline double tc_aabb_surface_area(tc_aabb box) {
    tc_vec3 d = tc_aabb_size(box);
    return 2.0 * (d.x * d.y + d.y * d.z + d.z * d.x);
}

static inline double tc_aabb_volume(tc_aabb box) {
    tc_vec3 d = tc_aabb_size(box);
    return d.x * d.y * d.z;
}

static inline void tc_aabb_get_corners(tc_aabb box, tc_vec3* out_corners) {
    out_corners[0] = TC_VEC3(box.min_point.x, box.min_point.y, box.min_point.z);
    out_corners[1] = TC_VEC3(box.min_point.x, box.min_point.y, box.max_point.z);
    out_corners[2] = TC_VEC3(box.min_point.x, box.max_point.y, box.min_point.z);
    out_corners[3] = TC_VEC3(box.min_point.x, box.max_point.y, box.max_point.z);
    out_corners[4] = TC_VEC3(box.max_point.x, box.min_point.y, box.min_point.z);
    out_corners[5] = TC_VEC3(box.max_point.x, box.min_point.y, box.max_point.z);
    out_corners[6] = TC_VEC3(box.max_point.x, box.max_point.y, box.min_point.z);
    out_corners[7] = TC_VEC3(box.max_point.x, box.max_point.y, box.max_point.z);
}

static inline tc_aabb tc_aabb_from_points(const tc_vec3* points, size_t count) {
    if (count == 0) {
        return tc_aabb_zero();
    }
    tc_aabb result = tc_aabb_new(points[0], points[0]);
    for (size_t i = 1; i < count; ++i) {
        tc_aabb_extend(&result, points[i]);
    }
    return result;
}

static inline tc_aabb tc_aabb_transform_by_pose3(tc_aabb box, tc_pose3 pose) {
    tc_vec3 corners[8];
    tc_aabb_get_corners(box, corners);
    tc_aabb result = tc_aabb_new(
        tc_pose3_transform_point(pose, corners[0]),
        tc_pose3_transform_point(pose, corners[0])
    );
    for (size_t i = 1; i < 8; ++i) {
        tc_aabb_extend(&result, tc_pose3_transform_point(pose, corners[i]));
    }
    return result;
}

static inline tc_aabb tc_aabb_transform_by_gpose(tc_aabb box, tc_general_pose3 pose) {
    tc_vec3 corners[8];
    tc_aabb_get_corners(box, corners);
    tc_aabb result = tc_aabb_new(
        tc_gpose_transform_point(pose, corners[0]),
        tc_gpose_transform_point(pose, corners[0])
    );
    for (size_t i = 1; i < 8; ++i) {
        tc_aabb_extend(&result, tc_gpose_transform_point(pose, corners[i]));
    }
    return result;
}

#ifdef __cplusplus
}
#endif

#endif // TC_AABB_H
