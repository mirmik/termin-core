#include <geom/tc_affine3.h>
#include <geom/tc_quat.h>

#include "guard_c.h"

#include <math.h>
#include <stddef.h>

static int near(double a, double b, double epsilon) {
    return fabs(a - b) <= epsilon;
}

static int near_vec3(tc_vec3 a, tc_vec3 b, double epsilon) {
    return near(a.x, b.x, epsilon) && near(a.y, b.y, epsilon) && near(a.z, b.z, epsilon);
}

int main(void) {
    GUARD_C_CHECK(sizeof(tc_basis3d) == sizeof(double) * 9);
    GUARD_C_CHECK(offsetof(tc_basis3d, x) == sizeof(double) * 0);
    GUARD_C_CHECK(offsetof(tc_basis3d, y) == sizeof(double) * 3);
    GUARD_C_CHECK(offsetof(tc_basis3d, z) == sizeof(double) * 6);
    GUARD_C_CHECK(sizeof(tc_affine3d) == sizeof(double) * 12);
    GUARD_C_CHECK(offsetof(tc_affine3d, basis) == sizeof(double) * 0);
    GUARD_C_CHECK(offsetof(tc_affine3d, translation) == sizeof(double) * 9);

    tc_quat child_rotation = tc_quat_from_axis_angle(tc_vec3_unit_z(), 0.63);
    tc_affine3d parent = tc_affine3d_mul(tc_affine3d_translation(5.0, -3.0, 2.0), tc_affine3d_scaling(2.0, 0.5, 1.25));
    tc_affine3d child = tc_affine3d_trs(TC_VEC3(-1.0, 4.0, 0.75), child_rotation, TC_VEC3(0.8, 1.4, 2.0));
    tc_vec3 point = TC_VEC3(3.0, -2.0, 1.5);
    tc_vec3 sequential = tc_affine3d_transform_point(parent, tc_affine3d_transform_point(child, point));
    tc_affine3d composed_affine = tc_affine3d_mul(parent, child);
    tc_vec3 composed = tc_affine3d_transform_point(composed_affine, point);
    GUARD_C_CHECK(near_vec3(sequential, composed, 1.0e-12));

    // Non-uniform parent scale and rotated child produce non-orthogonal
    // columns. Exact affine composition must retain that shear.
    double xy_dot = tc_vec3_dot(composed_affine.basis.x, composed_affine.basis.y);
    GUARD_C_CHECK(fabs(xy_dot) > 1.0e-3);

    tc_affine3d reflection = tc_affine3d_mul(tc_affine3d_translation(7.0, -5.0, 3.0),
                                             tc_affine3d_mul(tc_affine3d_rotation(tc_quat_from_euler(0.2, -0.4, 0.7)),
                                                             tc_affine3d_scaling(-2.0, 0.75, 1.5)));
    tc_affine3d inverse = tc_affine3d_identity();
    GUARD_C_CHECK(tc_affine3d_try_inverse(reflection, 1.0e-12, &inverse));
    tc_vec3 round_trip = tc_affine3d_transform_point(inverse, tc_affine3d_transform_point(reflection, point));
    GUARD_C_CHECK(near_vec3(round_trip, point, 1.0e-11));

    tc_affine3d unchanged = tc_affine3d_translation(9.0, 11.0, 13.0);
    GUARD_C_CHECK(!tc_affine3d_try_inverse(tc_affine3d_scaling(0.0, 2.0, 3.0), 1.0e-12, &unchanged));
    GUARD_C_CHECK(unchanged.translation.x == 9.0);
    GUARD_C_CHECK(unchanged.translation.y == 11.0);
    GUARD_C_CHECK(unchanged.translation.z == 13.0);
    GUARD_C_CHECK(!tc_affine3d_try_inverse(tc_affine3d_identity(), 1.0e-12, NULL));

    double matrix[16];
    tc_affine3d_to_matrix4(composed_affine, matrix);
    GUARD_C_CHECK(matrix[3] == 0.0);
    GUARD_C_CHECK(matrix[7] == 0.0);
    GUARD_C_CHECK(matrix[11] == 0.0);
    GUARD_C_CHECK(matrix[15] == 1.0);

    tc_affine3d matrix_round_trip = tc_affine3d_identity();
    GUARD_C_CHECK(tc_affine3d_try_from_matrix4(matrix, 1.0e-12, &matrix_round_trip));
    GUARD_C_CHECK(near_vec3(tc_affine3d_transform_point(matrix_round_trip, point), composed, 1.0e-12));

    matrix[3] = 0.25;
    GUARD_C_CHECK(!tc_affine3d_try_from_matrix4(matrix, 1.0e-12, &matrix_round_trip));

    return 0;
}
