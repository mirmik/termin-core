#include <geom/tc_affine2.h>

#include "guard_c.h"

#include <math.h>
#include <stddef.h>

static int nearf(float a, float b, float epsilon) {
    return fabsf(a - b) <= epsilon;
}

int main(void) {
    GUARD_C_CHECK(sizeof(tc_vec2f) == sizeof(float) * 2);
    GUARD_C_CHECK(sizeof(tc_size2f) == sizeof(float) * 2);
    GUARD_C_CHECK(sizeof(tc_rect2f) == sizeof(float) * 4);
    GUARD_C_CHECK(sizeof(tc_bounds2f) == sizeof(float) * 4);
    GUARD_C_CHECK(sizeof(tc_affine2f) == sizeof(float) * 6);
    GUARD_C_CHECK(offsetof(tc_affine2f, m00) == sizeof(float) * 0);
    GUARD_C_CHECK(offsetof(tc_affine2f, m01) == sizeof(float) * 1);
    GUARD_C_CHECK(offsetof(tc_affine2f, m10) == sizeof(float) * 2);
    GUARD_C_CHECK(offsetof(tc_affine2f, m11) == sizeof(float) * 3);
    GUARD_C_CHECK(offsetof(tc_affine2f, tx) == sizeof(float) * 4);
    GUARD_C_CHECK(offsetof(tc_affine2f, ty) == sizeof(float) * 5);

    tc_affine2f parent = tc_affine2f_mul(tc_affine2f_translation(5.0f, -3.0f), tc_affine2f_scaling(2.0f, 0.5f));
    tc_affine2f child = tc_affine2f_mul(tc_affine2f_rotation(0.6f), tc_affine2f_shear(0.25f, -0.4f));
    tc_vec2f point = TC_VEC2F(3.0f, -2.0f);
    tc_vec2f sequential = tc_affine2f_transform_point(parent, tc_affine2f_transform_point(child, point));
    tc_vec2f composed = tc_affine2f_transform_point(tc_affine2f_mul(parent, child), point);
    GUARD_C_CHECK(nearf(sequential.x, composed.x, 1.0e-5f));
    GUARD_C_CHECK(nearf(sequential.y, composed.y, 1.0e-5f));

    tc_affine2f reflection =
        tc_affine2f_mul(tc_affine2f_translation(7.0f, -5.0f),
                        tc_affine2f_mul(tc_affine2f_rotation(0.37f), tc_affine2f_scaling(-2.0f, 0.75f)));
    tc_affine2f inverse = tc_affine2f_identity();
    GUARD_C_CHECK(tc_affine2f_try_inverse(reflection, 1.0e-8f, &inverse));
    tc_vec2f round_trip = tc_affine2f_transform_point(inverse, tc_affine2f_transform_point(reflection, point));
    GUARD_C_CHECK(nearf(round_trip.x, point.x, 1.0e-4f));
    GUARD_C_CHECK(nearf(round_trip.y, point.y, 1.0e-4f));

    tc_affine2f unchanged = tc_affine2f_translation(9.0f, 11.0f);
    GUARD_C_CHECK(!tc_affine2f_try_inverse(tc_affine2f_scaling(0.0f, 2.0f), 1.0e-8f, &unchanged));
    GUARD_C_CHECK(unchanged.tx == 9.0f);
    GUARD_C_CHECK(unchanged.ty == 11.0f);
    GUARD_C_CHECK(!tc_affine2f_try_inverse(tc_affine2f_identity(), 1.0e-8f, NULL));

    tc_bounds2f bounds = TC_BOUNDS2F(-2.0f, -1.0f, 3.0f, 4.0f);
    tc_bounds2f transformed = tc_affine2f_transform_bounds(child, bounds);
    tc_vec2f corners[] = {
        TC_VEC2F(bounds.x0, bounds.y0),
        TC_VEC2F(bounds.x1, bounds.y0),
        TC_VEC2F(bounds.x0, bounds.y1),
        TC_VEC2F(bounds.x1, bounds.y1),
    };
    for (size_t i = 0; i < 4; ++i) {
        tc_vec2f p = tc_affine2f_transform_point(child, corners[i]);
        GUARD_C_CHECK(p.x >= transformed.x0 - 1.0e-5f);
        GUARD_C_CHECK(p.x <= transformed.x1 + 1.0e-5f);
        GUARD_C_CHECK(p.y >= transformed.y0 - 1.0e-5f);
        GUARD_C_CHECK(p.y <= transformed.y1 + 1.0e-5f);
    }

    tc_pose2 pose = {
        .ang = 0.75,
        .lin = {4.0, -6.0},
    };
    tc_affine2f from_pose = tc_affine2f_from_pose2(pose);
    tc_vec2f pose_point = tc_affine2f_transform_point(from_pose, point);
    double c = cos(pose.ang);
    double s = sin(pose.ang);
    GUARD_C_CHECK(nearf(pose_point.x, (float)(c * point.x - s * point.y + pose.lin.x), 1.0e-5f));
    GUARD_C_CHECK(nearf(pose_point.y, (float)(s * point.x + c * point.y + pose.lin.y), 1.0e-5f));

    return 0;
}
