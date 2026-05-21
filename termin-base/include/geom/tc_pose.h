// tc_pose.h - Pose types (position + rotation + optional scale)
#ifndef TC_POSE_H
#define TC_POSE_H

#include <tcbase/tc_types.h>
#include "geom/tc_vec3.h"
#include "geom/tc_quat.h"

// C/C++ compatible struct initialization
// Layout: rotation first, then position (matches C++ Pose3/GeneralPose3)
#ifdef __cplusplus
    #define TC_POSE3(rot, pos) tc_pose3{rot, pos}
    #define TC_GPOSE(rot, pos, scl) tc_general_pose3{rot, pos, scl}
#else
    #define TC_POSE3(rot, pos) (tc_pose3){rot, pos}
    #define TC_GPOSE(rot, pos, scl) (tc_general_pose3){rot, pos, scl}
#endif

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Pose3 (rotation + position, no scale)
// ============================================================================

static inline tc_pose3 tc_pose3_identity(void) {
    return TC_POSE3(tc_quat_identity(), tc_vec3_zero());
}

static inline tc_pose3 tc_pose3_new(tc_quat rot, tc_vec3 pos) {
    return TC_POSE3(rot, pos);
}

static inline tc_pose3 tc_pose3_from_position(tc_vec3 pos) {
    return TC_POSE3(tc_quat_identity(), pos);
}

static inline tc_pose3 tc_pose3_from_rotation(tc_quat rot) {
    return TC_POSE3(rot, tc_vec3_zero());
}

// Composition: parent * child
static inline tc_pose3 tc_pose3_mul(tc_pose3 parent, tc_pose3 child) {
    return TC_POSE3(
        tc_quat_mul(parent.rotation, child.rotation),
        tc_vec3_add(parent.position, tc_quat_rotate(parent.rotation, child.position))
    );
}

static inline tc_pose3 tc_pose3_inverse(tc_pose3 p) {
    tc_quat inv_rot = tc_quat_inverse(p.rotation);
    return TC_POSE3(
        inv_rot,
        tc_quat_rotate(inv_rot, tc_vec3_neg(p.position))
    );
}

static inline tc_vec3 tc_pose3_transform_point(tc_pose3 p, tc_vec3 point) {
    return tc_vec3_add(p.position, tc_quat_rotate(p.rotation, point));
}

static inline tc_vec3 tc_pose3_transform_vector(tc_pose3 p, tc_vec3 vec) {
    return tc_quat_rotate(p.rotation, vec);
}

// ============================================================================
// GeneralPose3 (rotation + position + scale)
// ============================================================================

static inline tc_general_pose3 tc_gpose_identity(void) {
    return TC_GPOSE(tc_quat_identity(), tc_vec3_zero(), tc_vec3_one());
}

static inline tc_general_pose3 tc_gpose_new(tc_quat rot, tc_vec3 pos, tc_vec3 scale) {
    return TC_GPOSE(rot, pos, scale);
}

static inline tc_general_pose3 tc_gpose_from_pose(tc_pose3 p) {
    return TC_GPOSE(p.rotation, p.position, tc_vec3_one());
}

static inline tc_pose3 tc_gpose_to_pose(tc_general_pose3 gp) {
    return TC_POSE3(gp.rotation, gp.position);
}

// Composition: parent * child (with scale inheritance)
static inline tc_general_pose3 tc_gpose_mul(tc_general_pose3 parent, tc_general_pose3 child) {
    tc_vec3 scaled_child = tc_vec3_mul(parent.scale, child.position);
    tc_vec3 rotated_child = tc_quat_rotate(parent.rotation, scaled_child);

    return TC_GPOSE(
        tc_quat_mul(parent.rotation, child.rotation),
        tc_vec3_add(parent.position, rotated_child),
        tc_vec3_mul(parent.scale, child.scale)
    );
}

// Inverse (approximate for non-uniform scale)
static inline tc_general_pose3 tc_gpose_inverse(tc_general_pose3 p) {
    tc_quat inv_rot = tc_quat_inverse(p.rotation);
    tc_vec3 inv_scale = TC_VEC3(1.0 / p.scale.x, 1.0 / p.scale.y, 1.0 / p.scale.z);
    tc_vec3 neg_pos = tc_vec3_neg(p.position);
    tc_vec3 rotated = tc_quat_rotate(inv_rot, neg_pos);
    tc_vec3 scaled = tc_vec3_mul(inv_scale, rotated);

    return TC_GPOSE(inv_rot, scaled, inv_scale);
}

static inline tc_vec3 tc_gpose_transform_point(tc_general_pose3 p, tc_vec3 point) {
    tc_vec3 scaled = tc_vec3_mul(p.scale, point);
    tc_vec3 rotated = tc_quat_rotate(p.rotation, scaled);
    return tc_vec3_add(p.position, rotated);
}

static inline tc_vec3 tc_gpose_transform_vector(tc_general_pose3 p, tc_vec3 vec) {
    tc_vec3 scaled = tc_vec3_mul(p.scale, vec);
    return tc_quat_rotate(p.rotation, scaled);
}

// ============================================================================
// Matrix conversion
// ============================================================================

// Fill 4x4 column-major matrix from Pose3 (no scale)
static inline void tc_pose3_to_matrix(tc_pose3 p, double* out) {
    double xx = p.rotation.x * p.rotation.x;
    double yy = p.rotation.y * p.rotation.y;
    double zz = p.rotation.z * p.rotation.z;
    double xy = p.rotation.x * p.rotation.y;
    double xz = p.rotation.x * p.rotation.z;
    double yz = p.rotation.y * p.rotation.z;
    double wx = p.rotation.w * p.rotation.x;
    double wy = p.rotation.w * p.rotation.y;
    double wz = p.rotation.w * p.rotation.z;

    // Column 0
    out[0] = 1.0 - 2.0 * (yy + zz);
    out[1] = 2.0 * (xy + wz);
    out[2] = 2.0 * (xz - wy);
    out[3] = 0.0;

    // Column 1
    out[4] = 2.0 * (xy - wz);
    out[5] = 1.0 - 2.0 * (xx + zz);
    out[6] = 2.0 * (yz + wx);
    out[7] = 0.0;

    // Column 2
    out[8]  = 2.0 * (xz + wy);
    out[9]  = 2.0 * (yz - wx);
    out[10] = 1.0 - 2.0 * (xx + yy);
    out[11] = 0.0;

    // Column 3 (translation)
    out[12] = p.position.x;
    out[13] = p.position.y;
    out[14] = p.position.z;
    out[15] = 1.0;
}

// Fill 4x4 column-major matrix from GeneralPose3
static inline void tc_gpose_to_mat44(tc_general_pose3 p, tc_mat44* out) {
    double xx = p.rotation.x * p.rotation.x;
    double yy = p.rotation.y * p.rotation.y;
    double zz = p.rotation.z * p.rotation.z;
    double xy = p.rotation.x * p.rotation.y;
    double xz = p.rotation.x * p.rotation.z;
    double yz = p.rotation.y * p.rotation.z;
    double wx = p.rotation.w * p.rotation.x;
    double wy = p.rotation.w * p.rotation.y;
    double wz = p.rotation.w * p.rotation.z;

    double sx = p.scale.x, sy = p.scale.y, sz = p.scale.z;

    // Column 0
    out->m[0] = sx * (1.0 - 2.0 * (yy + zz));
    out->m[1] = sx * 2.0 * (xy + wz);
    out->m[2] = sx * 2.0 * (xz - wy);
    out->m[3] = 0.0;

    // Column 1
    out->m[4] = sy * 2.0 * (xy - wz);
    out->m[5] = sy * (1.0 - 2.0 * (xx + zz));
    out->m[6] = sy * 2.0 * (yz + wx);
    out->m[7] = 0.0;

    // Column 2
    out->m[8]  = sz * 2.0 * (xz + wy);
    out->m[9]  = sz * 2.0 * (yz - wx);
    out->m[10] = sz * (1.0 - 2.0 * (xx + yy));
    out->m[11] = 0.0;

    // Column 3 (translation)
    out->m[12] = p.position.x;
    out->m[13] = p.position.y;
    out->m[14] = p.position.z;
    out->m[15] = 1.0;
}

// Interpolation
static inline tc_general_pose3 tc_gpose_lerp(tc_general_pose3 a, tc_general_pose3 b, double t) {
    return TC_GPOSE(
        tc_quat_slerp(a.rotation, b.rotation, t),
        tc_vec3_lerp(a.position, b.position, t),
        tc_vec3_lerp(a.scale, b.scale, t)
    );
}

#ifdef __cplusplus
}
#endif

#endif // TC_POSE_H
