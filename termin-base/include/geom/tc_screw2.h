// tc_screw2.h - 2D screw/twist/wrench operations
#ifndef TC_SCREW2_H
#define TC_SCREW2_H

#include <tcbase/tc_types.h>
#include "geom/tc_pose2.h"
#include "geom/tc_vec2.h"

#ifdef __cplusplus
    #define TC_SCREW2(ang_, lin_) tc_screw2{ang_, lin_}
#else
    #define TC_SCREW2(ang_, lin_) (tc_screw2){ang_, lin_}
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline tc_screw2 tc_screw2_new(double ang, tc_vec2 lin) {
    return TC_SCREW2(ang, lin);
}

static inline tc_screw2 tc_screw2_zero(void) {
    return TC_SCREW2(0.0, tc_vec2_zero());
}

static inline tc_screw2 tc_screw2_add(tc_screw2 a, tc_screw2 b) {
    return TC_SCREW2(a.ang + b.ang, tc_vec2_add(a.lin, b.lin));
}

static inline tc_screw2 tc_screw2_sub(tc_screw2 a, tc_screw2 b) {
    return TC_SCREW2(a.ang - b.ang, tc_vec2_sub(a.lin, b.lin));
}

static inline tc_screw2 tc_screw2_scale(tc_screw2 s, double k) {
    return TC_SCREW2(s.ang * k, tc_vec2_scale(s.lin, k));
}

static inline tc_screw2 tc_screw2_neg(tc_screw2 s) {
    return TC_SCREW2(-s.ang, tc_vec2_neg(s.lin));
}

static inline tc_vec2 tc_screw2_scalar_cross_vec(double scalar, tc_vec2 vec) {
    return TC_VEC2(scalar * vec.y, -scalar * vec.x);
}

static inline tc_vec2 tc_screw2_vec_cross_scalar(tc_vec2 vec, double scalar) {
    return TC_VEC2(-scalar * vec.y, scalar * vec.x);
}

static inline tc_screw2 tc_screw2_kinematic_carry(tc_screw2 s, tc_vec2 arm) {
    return TC_SCREW2(s.ang, tc_vec2_add(s.lin, tc_screw2_scalar_cross_vec(s.ang, arm)));
}

static inline tc_screw2 tc_screw2_force_carry(tc_screw2 s, tc_vec2 arm) {
    return TC_SCREW2(s.ang - tc_vec2_cross(arm, s.lin), s.lin);
}

static inline tc_screw2 tc_screw2_transform_by(tc_screw2 s, tc_pose2 pose) {
    return TC_SCREW2(s.ang, tc_pose2_transform_vector(pose, s.lin));
}

static inline tc_screw2 tc_screw2_inverse_transform_by(tc_screw2 s, tc_pose2 pose) {
    return TC_SCREW2(s.ang, tc_pose2_inverse_transform_vector(pose, s.lin));
}

static inline tc_screw2 tc_screw2_transform_as_twist_by(tc_screw2 s, tc_pose2 pose) {
    tc_vec2 rlin = tc_pose2_transform_vector(pose, s.lin);
    return TC_SCREW2(s.ang, tc_vec2_add(rlin, tc_screw2_vec_cross_scalar(pose.lin, s.ang)));
}

static inline tc_screw2 tc_screw2_inverse_transform_as_twist_by(tc_screw2 s, tc_pose2 pose) {
    tc_vec2 shifted = tc_vec2_sub(s.lin, tc_screw2_vec_cross_scalar(pose.lin, s.ang));
    return TC_SCREW2(s.ang, tc_pose2_inverse_transform_vector(pose, shifted));
}

static inline tc_screw2 tc_screw2_transform_as_wrench_by(tc_screw2 s, tc_pose2 pose) {
    return TC_SCREW2(
        s.ang + tc_vec2_cross(pose.lin, s.lin),
        tc_pose2_transform_vector(pose, s.lin)
    );
}

static inline tc_screw2 tc_screw2_inverse_transform_as_wrench_by(tc_screw2 s, tc_pose2 pose) {
    return TC_SCREW2(
        s.ang - tc_vec2_cross(pose.lin, s.lin),
        tc_pose2_inverse_transform_vector(pose, s.lin)
    );
}

static inline tc_pose2 tc_screw2_to_pose(tc_screw2 s) {
    return tc_pose2_new(s.ang, s.lin);
}

#ifdef __cplusplus
}
#endif

#endif // TC_SCREW2_H
