// tc_vec2.h - 2D vector operations
#ifndef TC_VEC2_H
#define TC_VEC2_H

#include <tcbase/tc_types.h>
#include <math.h>

#ifdef __cplusplus
    #define TC_VEC2(x, y) tc_vec2{x, y}
#else
    #define TC_VEC2(x, y) (tc_vec2){x, y}
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline tc_vec2 tc_vec2_new(double x, double y) {
    return TC_VEC2(x, y);
}

static inline tc_vec2 tc_vec2_zero(void) {
    return TC_VEC2(0.0, 0.0);
}

static inline tc_vec2 tc_vec2_unit_x(void) {
    return TC_VEC2(1.0, 0.0);
}

static inline tc_vec2 tc_vec2_unit_y(void) {
    return TC_VEC2(0.0, 1.0);
}

static inline tc_vec2 tc_vec2_add(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(a.x + b.x, a.y + b.y);
}

static inline tc_vec2 tc_vec2_sub(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(a.x - b.x, a.y - b.y);
}

static inline tc_vec2 tc_vec2_scale(tc_vec2 v, double s) {
    return TC_VEC2(v.x * s, v.y * s);
}

static inline tc_vec2 tc_vec2_neg(tc_vec2 v) {
    return TC_VEC2(-v.x, -v.y);
}

static inline double tc_vec2_dot(tc_vec2 a, tc_vec2 b) {
    return a.x * b.x + a.y * b.y;
}

static inline double tc_vec2_cross(tc_vec2 a, tc_vec2 b) {
    return a.x * b.y - a.y * b.x;
}

static inline double tc_vec2_length_sq(tc_vec2 v) {
    return v.x * v.x + v.y * v.y;
}

static inline double tc_vec2_length(tc_vec2 v) {
    return sqrt(tc_vec2_length_sq(v));
}

static inline tc_vec2 tc_vec2_lerp(tc_vec2 a, tc_vec2 b, double t) {
    return TC_VEC2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t);
}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC2_H
