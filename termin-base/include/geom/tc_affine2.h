// tc_affine2.h - Exact packed 2D affine transform operations.
#ifndef TC_AFFINE2_H
#define TC_AFFINE2_H

#include <math.h>
#include <stdbool.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_AFFINE2F(m00_, m01_, m10_, m11_, tx_, ty_) \
    tc_affine2f{m00_, m01_, m10_, m11_, tx_, ty_}
#define TC_VEC2F(x_, y_) tc_vec2f{x_, y_}
#define TC_BOUNDS2F(x0_, y0_, x1_, y1_) tc_bounds2f{x0_, y0_, x1_, y1_}
#else
#define TC_AFFINE2F(m00_, m01_, m10_, m11_, tx_, ty_) \
    (tc_affine2f){m00_, m01_, m10_, m11_, tx_, ty_}
#define TC_VEC2F(x_, y_) (tc_vec2f){x_, y_}
#define TC_BOUNDS2F(x0_, y0_, x1_, y1_) \
    (tc_bounds2f){x0_, y0_, x1_, y1_}
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline tc_affine2f tc_affine2f_new(
    float m00,
    float m01,
    float m10,
    float m11,
    float tx,
    float ty) {
    return TC_AFFINE2F(m00, m01, m10, m11, tx, ty);
}

static inline tc_affine2f tc_affine2f_identity(void) {
    return TC_AFFINE2F(1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f);
}

static inline tc_affine2f tc_affine2f_translation(float x, float y) {
    return TC_AFFINE2F(1.0f, 0.0f, 0.0f, 1.0f, x, y);
}

static inline tc_affine2f tc_affine2f_rotation(float radians) {
    float c = cosf(radians);
    float s = sinf(radians);
    return TC_AFFINE2F(c, -s, s, c, 0.0f, 0.0f);
}

static inline tc_affine2f tc_affine2f_scaling(float sx, float sy) {
    return TC_AFFINE2F(sx, 0.0f, 0.0f, sy, 0.0f, 0.0f);
}

// x_by_y changes x as y grows; y_by_x changes y as x grows.
static inline tc_affine2f tc_affine2f_shear(float x_by_y, float y_by_x) {
    return TC_AFFINE2F(1.0f, x_by_y, y_by_x, 1.0f, 0.0f, 0.0f);
}

// T * R * S for column vectors.
static inline tc_affine2f tc_affine2f_trs(
    tc_vec2f translation,
    float radians,
    tc_vec2f scale) {
    float c = cosf(radians);
    float s = sinf(radians);
    return TC_AFFINE2F(
        c * scale.x,
        -s * scale.y,
        s * scale.x,
        c * scale.y,
        translation.x,
        translation.y);
}

static inline tc_affine2f tc_affine2f_from_pose2(tc_pose2 pose) {
    float c = (float)cos(pose.ang);
    float s = (float)sin(pose.ang);
    return TC_AFFINE2F(
        c,
        -s,
        s,
        c,
        (float)pose.lin.x,
        (float)pose.lin.y);
}

// parent * child applies child first, then parent.
static inline tc_affine2f tc_affine2f_mul(
    tc_affine2f parent,
    tc_affine2f child) {
    return TC_AFFINE2F(
        parent.m00 * child.m00 + parent.m01 * child.m10,
        parent.m00 * child.m01 + parent.m01 * child.m11,
        parent.m10 * child.m00 + parent.m11 * child.m10,
        parent.m10 * child.m01 + parent.m11 * child.m11,
        parent.m00 * child.tx + parent.m01 * child.ty + parent.tx,
        parent.m10 * child.tx + parent.m11 * child.ty + parent.ty);
}

static inline tc_vec2f tc_affine2f_transform_point(
    tc_affine2f affine,
    tc_vec2f point) {
    return TC_VEC2F(
        affine.m00 * point.x + affine.m01 * point.y + affine.tx,
        affine.m10 * point.x + affine.m11 * point.y + affine.ty);
}

static inline tc_vec2f tc_affine2f_transform_vector(
    tc_affine2f affine,
    tc_vec2f vector) {
    return TC_VEC2F(
        affine.m00 * vector.x + affine.m01 * vector.y,
        affine.m10 * vector.x + affine.m11 * vector.y);
}

static inline float tc_affine2f_determinant(tc_affine2f affine) {
    return affine.m00 * affine.m11 - affine.m01 * affine.m10;
}

static inline bool tc_affine2f_is_finite(tc_affine2f affine) {
    return isfinite(affine.m00)
        && isfinite(affine.m01)
        && isfinite(affine.m10)
        && isfinite(affine.m11)
        && isfinite(affine.tx)
        && isfinite(affine.ty);
}

static inline bool tc_affine2f_try_inverse(
    tc_affine2f affine,
    float epsilon,
    tc_affine2f* out_inverse) {
    if (out_inverse == NULL || !tc_affine2f_is_finite(affine)) {
        return false;
    }

    float determinant = tc_affine2f_determinant(affine);
    float threshold = fabsf(epsilon);
    if (!isfinite(determinant) || fabsf(determinant) <= threshold) {
        return false;
    }

    float inv_det = 1.0f / determinant;
    tc_affine2f inverse = TC_AFFINE2F(
        affine.m11 * inv_det,
        -affine.m01 * inv_det,
        -affine.m10 * inv_det,
        affine.m00 * inv_det,
        0.0f,
        0.0f);
    inverse.tx = -(inverse.m00 * affine.tx + inverse.m01 * affine.ty);
    inverse.ty = -(inverse.m10 * affine.tx + inverse.m11 * affine.ty);
    *out_inverse = inverse;
    return true;
}

static inline tc_bounds2f tc_affine2f_transform_bounds(
    tc_affine2f affine,
    tc_bounds2f bounds) {
    tc_vec2f p0 = tc_affine2f_transform_point(
        affine, TC_VEC2F(bounds.x0, bounds.y0));
    tc_vec2f p1 = tc_affine2f_transform_point(
        affine, TC_VEC2F(bounds.x1, bounds.y0));
    tc_vec2f p2 = tc_affine2f_transform_point(
        affine, TC_VEC2F(bounds.x0, bounds.y1));
    tc_vec2f p3 = tc_affine2f_transform_point(
        affine, TC_VEC2F(bounds.x1, bounds.y1));

    return TC_BOUNDS2F(
        fminf(fminf(p0.x, p1.x), fminf(p2.x, p3.x)),
        fminf(fminf(p0.y, p1.y), fminf(p2.y, p3.y)),
        fmaxf(fmaxf(p0.x, p1.x), fmaxf(p2.x, p3.x)),
        fmaxf(fmaxf(p0.y, p1.y), fmaxf(p2.y, p3.y)));
}

#ifdef __cplusplus
}
#endif

#endif // TC_AFFINE2_H
