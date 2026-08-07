// tc_affine3.h - Exact packed double-precision 3D affine operations.
#ifndef TC_AFFINE3_H
#define TC_AFFINE3_H

#include <math.h>
#include <stdbool.h>
#include <stddef.h>

#include <geom/tc_vec3.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_BASIS3D(x_, y_, z_)                                                                                         \
    tc_basis3d {                                                                                                       \
        x_, y_, z_                                                                                                     \
    }
#define TC_AFFINE3D(basis_, translation_)                                                                              \
    tc_affine3d {                                                                                                      \
        basis_, translation_                                                                                           \
    }
#else
#define TC_BASIS3D(x_, y_, z_)                                                                                         \
    (tc_basis3d) {                                                                                                     \
        x_, y_, z_                                                                                                     \
    }
#define TC_AFFINE3D(basis_, translation_)                                                                              \
    (tc_affine3d) {                                                                                                    \
        basis_, translation_                                                                                           \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_basis3d tc_basis3d_new(tc_vec3 x, tc_vec3 y, tc_vec3 z) {
    return TC_BASIS3D(x, y, z);
}

TC_C_STATIC_INLINE tc_basis3d tc_basis3d_identity(void) {
    return TC_BASIS3D(TC_VEC3(1.0, 0.0, 0.0), TC_VEC3(0.0, 1.0, 0.0), TC_VEC3(0.0, 0.0, 1.0));
}

// rotation must be a unit quaternion, matching the existing Pose3 contract.
TC_C_STATIC_INLINE tc_basis3d tc_basis3d_from_quat(tc_quat rotation) {
    double xx = rotation.x * rotation.x;
    double yy = rotation.y * rotation.y;
    double zz = rotation.z * rotation.z;
    double xy = rotation.x * rotation.y;
    double xz = rotation.x * rotation.z;
    double yz = rotation.y * rotation.z;
    double wx = rotation.w * rotation.x;
    double wy = rotation.w * rotation.y;
    double wz = rotation.w * rotation.z;

    return TC_BASIS3D(TC_VEC3(1.0 - 2.0 * (yy + zz), 2.0 * (xy + wz), 2.0 * (xz - wy)),
                      TC_VEC3(2.0 * (xy - wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz + wx)),
                      TC_VEC3(2.0 * (xz + wy), 2.0 * (yz - wx), 1.0 - 2.0 * (xx + yy)));
}

TC_C_STATIC_INLINE tc_basis3d tc_basis3d_scaling(double sx, double sy, double sz) {
    return TC_BASIS3D(TC_VEC3(sx, 0.0, 0.0), TC_VEC3(0.0, sy, 0.0), TC_VEC3(0.0, 0.0, sz));
}

TC_C_STATIC_INLINE tc_vec3 tc_basis3d_transform_vector(tc_basis3d basis, tc_vec3 vector) {
    return TC_VEC3(basis.x.x * vector.x + basis.y.x * vector.y + basis.z.x * vector.z,
                   basis.x.y * vector.x + basis.y.y * vector.y + basis.z.y * vector.z,
                   basis.x.z * vector.x + basis.y.z * vector.y + basis.z.z * vector.z);
}

// parent * child applies child first, then parent.
TC_C_STATIC_INLINE tc_basis3d tc_basis3d_mul(tc_basis3d parent, tc_basis3d child) {
    return TC_BASIS3D(tc_basis3d_transform_vector(parent, child.x),
                      tc_basis3d_transform_vector(parent, child.y),
                      tc_basis3d_transform_vector(parent, child.z));
}

TC_C_STATIC_INLINE double tc_basis3d_determinant(tc_basis3d basis) {
    return basis.x.x * (basis.y.y * basis.z.z - basis.y.z * basis.z.y) -
           basis.y.x * (basis.x.y * basis.z.z - basis.x.z * basis.z.y) +
           basis.z.x * (basis.x.y * basis.y.z - basis.x.z * basis.y.y);
}

TC_C_STATIC_INLINE bool tc_basis3d_is_finite(tc_basis3d basis) {
    return isfinite(basis.x.x) && isfinite(basis.x.y) && isfinite(basis.x.z) && isfinite(basis.y.x) &&
           isfinite(basis.y.y) && isfinite(basis.y.z) && isfinite(basis.z.x) && isfinite(basis.z.y) &&
           isfinite(basis.z.z);
}

TC_C_STATIC_INLINE bool tc_basis3d_try_inverse(tc_basis3d basis, double epsilon, tc_basis3d* out_inverse) {
    if (out_inverse == NULL || !tc_basis3d_is_finite(basis)) {
        return false;
    }

    double determinant = tc_basis3d_determinant(basis);
    double threshold = fabs(epsilon);
    if (!isfinite(determinant) || fabs(determinant) <= threshold) {
        return false;
    }

    double inv_det = 1.0 / determinant;
    tc_vec3 row0 = TC_VEC3(basis.y.y * basis.z.z - basis.y.z * basis.z.y,
                           basis.y.z * basis.z.x - basis.y.x * basis.z.z,
                           basis.y.x * basis.z.y - basis.y.y * basis.z.x);
    tc_vec3 row1 = TC_VEC3(basis.z.y * basis.x.z - basis.z.z * basis.x.y,
                           basis.z.z * basis.x.x - basis.z.x * basis.x.z,
                           basis.z.x * basis.x.y - basis.z.y * basis.x.x);
    tc_vec3 row2 = TC_VEC3(basis.x.y * basis.y.z - basis.x.z * basis.y.y,
                           basis.x.z * basis.y.x - basis.x.x * basis.y.z,
                           basis.x.x * basis.y.y - basis.x.y * basis.y.x);

    *out_inverse = TC_BASIS3D(TC_VEC3(row0.x * inv_det, row1.x * inv_det, row2.x * inv_det),
                              TC_VEC3(row0.y * inv_det, row1.y * inv_det, row2.y * inv_det),
                              TC_VEC3(row0.z * inv_det, row1.z * inv_det, row2.z * inv_det));
    return true;
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_new(tc_basis3d basis, tc_vec3 translation) {
    return TC_AFFINE3D(basis, translation);
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_identity(void) {
    return TC_AFFINE3D(tc_basis3d_identity(), TC_VEC3(0.0, 0.0, 0.0));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_translation(double x, double y, double z) {
    return TC_AFFINE3D(tc_basis3d_identity(), TC_VEC3(x, y, z));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_rotation(tc_quat rotation) {
    return TC_AFFINE3D(tc_basis3d_from_quat(rotation), TC_VEC3(0.0, 0.0, 0.0));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_scaling(double sx, double sy, double sz) {
    return TC_AFFINE3D(tc_basis3d_scaling(sx, sy, sz), TC_VEC3(0.0, 0.0, 0.0));
}

// T * R * S for column vectors.
TC_C_STATIC_INLINE tc_affine3d tc_affine3d_trs(tc_vec3 translation, tc_quat rotation, tc_vec3 scale) {
    tc_basis3d basis = tc_basis3d_from_quat(rotation);
    basis.x = tc_vec3_scale(basis.x, scale.x);
    basis.y = tc_vec3_scale(basis.y, scale.y);
    basis.z = tc_vec3_scale(basis.z, scale.z);
    return TC_AFFINE3D(basis, translation);
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_from_pose3(tc_pose3 pose) {
    return tc_affine3d_trs(pose.lin, pose.ang, TC_VEC3(1.0, 1.0, 1.0));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_from_general_pose3(tc_general_pose3 pose) {
    return tc_affine3d_trs(pose.lin, pose.ang, pose.scale);
}

// parent * child applies child first, then parent.
TC_C_STATIC_INLINE tc_affine3d tc_affine3d_mul(tc_affine3d parent, tc_affine3d child) {
    return TC_AFFINE3D(tc_basis3d_mul(parent.basis, child.basis),
                       tc_vec3_add(parent.translation, tc_basis3d_transform_vector(parent.basis, child.translation)));
}

TC_C_STATIC_INLINE tc_vec3 tc_affine3d_transform_point(tc_affine3d affine, tc_vec3 point) {
    return tc_vec3_add(affine.translation, tc_basis3d_transform_vector(affine.basis, point));
}

TC_C_STATIC_INLINE tc_vec3 tc_affine3d_transform_vector(tc_affine3d affine, tc_vec3 vector) {
    return tc_basis3d_transform_vector(affine.basis, vector);
}

TC_C_STATIC_INLINE double tc_affine3d_determinant(tc_affine3d affine) {
    return tc_basis3d_determinant(affine.basis);
}

TC_C_STATIC_INLINE bool tc_affine3d_is_finite(tc_affine3d affine) {
    return tc_basis3d_is_finite(affine.basis) && isfinite(affine.translation.x) && isfinite(affine.translation.y) &&
           isfinite(affine.translation.z);
}

TC_C_STATIC_INLINE bool tc_affine3d_try_inverse(tc_affine3d affine, double epsilon, tc_affine3d* out_inverse) {
    if (out_inverse == NULL || !tc_affine3d_is_finite(affine)) {
        return false;
    }

    tc_basis3d inverse_basis;
    if (!tc_basis3d_try_inverse(affine.basis, epsilon, &inverse_basis)) {
        return false;
    }

    tc_vec3 inverse_translation = tc_basis3d_transform_vector(inverse_basis, tc_vec3_neg(affine.translation));
    *out_inverse = TC_AFFINE3D(inverse_basis, inverse_translation);
    return true;
}

// Expands to the public OpenGL-style column-major 4x4 convention.
TC_C_STATIC_INLINE void tc_affine3d_to_matrix4(tc_affine3d affine, double* out_column_major_16) {
    if (out_column_major_16 == NULL) {
        return;
    }

    out_column_major_16[0] = affine.basis.x.x;
    out_column_major_16[1] = affine.basis.x.y;
    out_column_major_16[2] = affine.basis.x.z;
    out_column_major_16[3] = 0.0;
    out_column_major_16[4] = affine.basis.y.x;
    out_column_major_16[5] = affine.basis.y.y;
    out_column_major_16[6] = affine.basis.y.z;
    out_column_major_16[7] = 0.0;
    out_column_major_16[8] = affine.basis.z.x;
    out_column_major_16[9] = affine.basis.z.y;
    out_column_major_16[10] = affine.basis.z.z;
    out_column_major_16[11] = 0.0;
    out_column_major_16[12] = affine.translation.x;
    out_column_major_16[13] = affine.translation.y;
    out_column_major_16[14] = affine.translation.z;
    out_column_major_16[15] = 1.0;
}

TC_C_STATIC_INLINE bool
tc_affine3d_try_from_matrix4(const double* column_major_16, double epsilon, tc_affine3d* out_affine) {
    if (column_major_16 == NULL || out_affine == NULL) {
        return false;
    }

    for (size_t i = 0; i < 16; ++i) {
        if (!isfinite(column_major_16[i])) {
            return false;
        }
    }

    double threshold = fabs(epsilon);
    if (fabs(column_major_16[3]) > threshold || fabs(column_major_16[7]) > threshold ||
        fabs(column_major_16[11]) > threshold || fabs(column_major_16[15] - 1.0) > threshold) {
        return false;
    }

    *out_affine = TC_AFFINE3D(TC_BASIS3D(TC_VEC3(column_major_16[0], column_major_16[1], column_major_16[2]),
                                         TC_VEC3(column_major_16[4], column_major_16[5], column_major_16[6]),
                                         TC_VEC3(column_major_16[8], column_major_16[9], column_major_16[10])),
                              TC_VEC3(column_major_16[12], column_major_16[13], column_major_16[14]));
    return true;
}

#ifdef __cplusplus
}
#endif

#endif // TC_AFFINE3_H
