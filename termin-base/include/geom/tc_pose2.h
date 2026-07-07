// tc_pose2.h - 2D pose operations
#ifndef TC_POSE2_H
#define TC_POSE2_H

#include <tcbase/tc_types.h>
#include "geom/tc_vec2.h"
#include <math.h>

#ifdef __cplusplus
    #define TC_POSE2(ang_, lin_) tc_pose2{ang_, lin_}
#else
    #define TC_POSE2(ang_, lin_) (tc_pose2){ang_, lin_}
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline tc_pose2 tc_pose2_new(double ang, tc_vec2 lin) {
    return TC_POSE2(ang, lin);
}

static inline tc_pose2 tc_pose2_identity(void) {
    return TC_POSE2(0.0, tc_vec2_zero());
}

static inline tc_vec2 tc_pose2_rotate_vector(tc_pose2 p, tc_vec2 v) {
    double c = cos(p.ang);
    double s = sin(p.ang);
    return TC_VEC2(c * v.x - s * v.y, s * v.x + c * v.y);
}

static inline tc_vec2 tc_pose2_inverse_rotate_vector(tc_pose2 p, tc_vec2 v) {
    double c = cos(p.ang);
    double s = sin(p.ang);
    return TC_VEC2(c * v.x + s * v.y, -s * v.x + c * v.y);
}

static inline tc_vec2 tc_pose2_transform_point(tc_pose2 p, tc_vec2 point) {
    return tc_vec2_add(tc_pose2_rotate_vector(p, point), p.lin);
}

static inline tc_vec2 tc_pose2_transform_vector(tc_pose2 p, tc_vec2 vec) {
    return tc_pose2_rotate_vector(p, vec);
}

static inline tc_vec2 tc_pose2_inverse_transform_point(tc_pose2 p, tc_vec2 point) {
    return tc_pose2_inverse_rotate_vector(p, tc_vec2_sub(point, p.lin));
}

static inline tc_vec2 tc_pose2_inverse_transform_vector(tc_pose2 p, tc_vec2 vec) {
    return tc_pose2_inverse_rotate_vector(p, vec);
}

static inline tc_pose2 tc_pose2_mul(tc_pose2 parent, tc_pose2 child) {
    return TC_POSE2(
        parent.ang + child.ang,
        tc_vec2_add(parent.lin, tc_pose2_rotate_vector(parent, child.lin))
    );
}

static inline tc_pose2 tc_pose2_inverse(tc_pose2 p) {
    double inv_ang = -p.ang;
    tc_pose2 inv_rot = TC_POSE2(inv_ang, tc_vec2_zero());
    return TC_POSE2(inv_ang, tc_pose2_rotate_vector(inv_rot, tc_vec2_neg(p.lin)));
}

static inline tc_pose2 tc_pose2_rotation(double angle) {
    return TC_POSE2(angle, tc_vec2_zero());
}

static inline tc_pose2 tc_pose2_translation(double x, double y) {
    return TC_POSE2(0.0, TC_VEC2(x, y));
}

static inline tc_pose2 tc_pose2_lerp(tc_pose2 a, tc_pose2 b, double t) {
    return TC_POSE2(
        a.ang + (b.ang - a.ang) * t,
        tc_vec2_lerp(a.lin, b.lin, t)
    );
}

static inline void tc_pose2_normalize_angle(tc_pose2* p) {
    p->ang = atan2(sin(p->ang), cos(p->ang));
}

#ifdef __cplusplus
}
#endif

#endif // TC_POSE2_H
