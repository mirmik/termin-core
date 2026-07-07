// tc_screw3.h - Spatial screw/twist/wrench operations
#ifndef TC_SCREW3_H
#define TC_SCREW3_H

#include <tcbase/tc_types.h>
#include "geom/tc_pose.h"
#include "geom/tc_vec3.h"

#ifdef __cplusplus
    #define TC_SCREW3(ang_, lin_) tc_screw3{ang_, lin_}
#else
    #define TC_SCREW3(ang_, lin_) (tc_screw3){ang_, lin_}
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline tc_screw3 tc_screw3_new(tc_vec3 ang, tc_vec3 lin) {
    return TC_SCREW3(ang, lin);
}

static inline tc_screw3 tc_screw3_zero(void) {
    return TC_SCREW3(tc_vec3_zero(), tc_vec3_zero());
}

static inline tc_screw3 tc_screw3_add(tc_screw3 a, tc_screw3 b) {
    return TC_SCREW3(tc_vec3_add(a.ang, b.ang), tc_vec3_add(a.lin, b.lin));
}

static inline tc_screw3 tc_screw3_sub(tc_screw3 a, tc_screw3 b) {
    return TC_SCREW3(tc_vec3_sub(a.ang, b.ang), tc_vec3_sub(a.lin, b.lin));
}

static inline tc_screw3 tc_screw3_scale(tc_screw3 s, double k) {
    return TC_SCREW3(tc_vec3_scale(s.ang, k), tc_vec3_scale(s.lin, k));
}

static inline tc_screw3 tc_screw3_neg(tc_screw3 s) {
    return TC_SCREW3(tc_vec3_neg(s.ang), tc_vec3_neg(s.lin));
}

static inline double tc_screw3_dot(tc_screw3 a, tc_screw3 b) {
    return tc_vec3_dot(a.ang, b.ang) + tc_vec3_dot(a.lin, b.lin);
}

static inline tc_screw3 tc_screw3_cross_motion(tc_screw3 a, tc_screw3 b) {
    return TC_SCREW3(
        tc_vec3_cross(a.ang, b.ang),
        tc_vec3_add(tc_vec3_cross(a.ang, b.lin), tc_vec3_cross(a.lin, b.ang))
    );
}

static inline tc_screw3 tc_screw3_cross_force(tc_screw3 a, tc_screw3 b) {
    return TC_SCREW3(
        tc_vec3_add(tc_vec3_cross(a.ang, b.ang), tc_vec3_cross(a.lin, b.lin)),
        tc_vec3_cross(a.ang, b.lin)
    );
}

static inline tc_screw3 tc_screw3_transform_by(tc_screw3 s, tc_pose3 pose) {
    return TC_SCREW3(
        tc_pose3_transform_vector(pose, s.ang),
        tc_pose3_transform_vector(pose, s.lin)
    );
}

static inline tc_screw3 tc_screw3_inverse_transform_by(tc_screw3 s, tc_pose3 pose) {
    tc_pose3 inv = tc_pose3_inverse(pose);
    return tc_screw3_transform_by(s, inv);
}

static inline tc_screw3 tc_screw3_adjoint_pose(tc_screw3 s, tc_pose3 pose) {
    tc_vec3 ang_world = tc_pose3_transform_vector(pose, s.ang);
    tc_vec3 lin_world = tc_vec3_add(
        tc_pose3_transform_vector(pose, s.lin),
        tc_vec3_cross(pose.lin, ang_world)
    );
    return TC_SCREW3(ang_world, lin_world);
}

static inline tc_screw3 tc_screw3_adjoint_arm(tc_screw3 s, tc_vec3 arm) {
    return TC_SCREW3(s.ang, tc_vec3_add(s.lin, tc_vec3_cross(s.ang, arm)));
}

static inline tc_screw3 tc_screw3_adjoint_inv_pose(tc_screw3 s, tc_pose3 pose) {
    return TC_SCREW3(
        tc_pose3_transform_vector(tc_pose3_inverse(pose), s.ang),
        tc_pose3_transform_vector(tc_pose3_inverse(pose), tc_vec3_sub(s.lin, tc_vec3_cross(pose.lin, s.ang)))
    );
}

static inline tc_screw3 tc_screw3_adjoint_inv_arm(tc_screw3 s, tc_vec3 arm) {
    return TC_SCREW3(s.ang, tc_vec3_sub(s.lin, tc_vec3_cross(s.ang, arm)));
}

static inline tc_screw3 tc_screw3_coadjoint_pose(tc_screw3 s, tc_pose3 pose) {
    tc_vec3 lin_world = tc_pose3_transform_vector(pose, s.lin);
    tc_vec3 ang_world = tc_vec3_add(
        tc_pose3_transform_vector(pose, s.ang),
        tc_vec3_cross(pose.lin, lin_world)
    );
    return TC_SCREW3(ang_world, lin_world);
}

static inline tc_screw3 tc_screw3_coadjoint_arm(tc_screw3 s, tc_vec3 arm) {
    return TC_SCREW3(tc_vec3_sub(s.ang, tc_vec3_cross(arm, s.lin)), s.lin);
}

static inline tc_screw3 tc_screw3_coadjoint_inv_pose(tc_screw3 s, tc_pose3 pose) {
    tc_pose3 inv = tc_pose3_inverse(pose);
    return TC_SCREW3(
        tc_pose3_transform_vector(inv, tc_vec3_sub(s.ang, tc_vec3_cross(pose.lin, s.lin))),
        tc_pose3_transform_vector(inv, s.lin)
    );
}

static inline tc_screw3 tc_screw3_coadjoint_inv_arm(tc_screw3 s, tc_vec3 arm) {
    return TC_SCREW3(tc_vec3_add(s.ang, tc_vec3_cross(arm, s.lin)), s.lin);
}

static inline tc_pose3 tc_screw3_to_pose(tc_screw3 s) {
    double theta = tc_vec3_length(s.ang);
    if (theta < 1e-8) {
        return tc_pose3_new(tc_quat_identity(), s.lin);
    }
    tc_vec3 axis = tc_vec3_scale(s.ang, 1.0 / theta);
    return tc_pose3_new(tc_quat_from_axis_angle(axis, theta), s.lin);
}

#ifdef __cplusplus
}
#endif

#endif // TC_SCREW3_H
