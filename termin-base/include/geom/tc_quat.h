// tc_quat.h - Quaternion operations
#ifndef TC_QUAT_H
#define TC_QUAT_H

#include <tcbase/tc_types.h>
#include "geom/tc_vec3.h"
#include <math.h>

// C/C++ compatible struct initialization
#ifdef __cplusplus
    #define TC_QUAT(x, y, z, w) tc_quat{x, y, z, w}
#else
    #define TC_QUAT(x, y, z, w) (tc_quat){x, y, z, w}
#endif

#ifdef __cplusplus
extern "C" {
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ============================================================================
// Constructors
// ============================================================================

static inline tc_quat tc_quat_new(double x, double y, double z, double w) {
    return TC_QUAT(x, y, z, w);
}

static inline tc_quat tc_quat_identity(void) {
    return TC_QUAT(0, 0, 0, 1);
}

// From axis-angle (axis should be normalized)
static inline tc_quat tc_quat_from_axis_angle(tc_vec3 axis, double angle) {
    double half = angle * 0.5;
    double s = sin(half);
    return TC_QUAT(axis.x * s, axis.y * s, axis.z * s, cos(half));
}

// From Euler angles (XYZ order, radians)
static inline tc_quat tc_quat_from_euler(double x, double y, double z) {
    double cx = cos(x * 0.5), sx = sin(x * 0.5);
    double cy = cos(y * 0.5), sy = sin(y * 0.5);
    double cz = cos(z * 0.5), sz = sin(z * 0.5);

    return TC_QUAT(
        sx * cy * cz - cx * sy * sz,
        cx * sy * cz + sx * cy * sz,
        cx * cy * sz - sx * sy * cz,
        cx * cy * cz + sx * sy * sz
    );
}

// ============================================================================
// Operations
// ============================================================================

static inline tc_quat tc_quat_mul(tc_quat a, tc_quat b) {
    return TC_QUAT(
        a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
        a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
        a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
    );
}

static inline tc_quat tc_quat_conjugate(tc_quat q) {
    return TC_QUAT(-q.x, -q.y, -q.z, q.w);
}

static inline double tc_quat_length_sq(tc_quat q) {
    return q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w;
}

static inline double tc_quat_length(tc_quat q) {
    return sqrt(tc_quat_length_sq(q));
}

static inline tc_quat tc_quat_normalize(tc_quat q) {
    double len = tc_quat_length(q);
    if (len < 1e-12) return tc_quat_identity();
    double inv = 1.0 / len;
    return TC_QUAT(q.x * inv, q.y * inv, q.z * inv, q.w * inv);
}

static inline tc_quat tc_quat_inverse(tc_quat q) {
    double len_sq = tc_quat_length_sq(q);
    if (len_sq < 1e-12) return tc_quat_identity();
    double inv = 1.0 / len_sq;
    return TC_QUAT(-q.x * inv, -q.y * inv, -q.z * inv, q.w * inv);
}

// ============================================================================
// Rotate vector by quaternion
// ============================================================================

static inline tc_vec3 tc_quat_rotate(tc_quat q, tc_vec3 v) {
    // q * v * q^-1 optimized
    tc_vec3 u = TC_VEC3(q.x, q.y, q.z);
    double s = q.w;

    tc_vec3 uv = tc_vec3_cross(u, v);
    tc_vec3 uuv = tc_vec3_cross(u, uv);

    return tc_vec3_add(v, tc_vec3_add(
        tc_vec3_scale(uv, 2.0 * s),
        tc_vec3_scale(uuv, 2.0)
    ));
}

// ============================================================================
// Interpolation
// ============================================================================

static inline tc_quat tc_quat_lerp(tc_quat a, tc_quat b, double t) {
    // Simple linear interpolation (not normalized)
    return TC_QUAT(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
        a.w + (b.w - a.w) * t
    );
}

static inline tc_quat tc_quat_nlerp(tc_quat a, tc_quat b, double t) {
    // Normalized linear interpolation
    double dot = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
    if (dot < 0) {
        b = TC_QUAT(-b.x, -b.y, -b.z, -b.w);
    }
    return tc_quat_normalize(tc_quat_lerp(a, b, t));
}

static inline tc_quat tc_quat_slerp(tc_quat a, tc_quat b, double t) {
    double dot = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;

    if (dot < 0) {
        b = TC_QUAT(-b.x, -b.y, -b.z, -b.w);
        dot = -dot;
    }

    if (dot > 0.9995) {
        return tc_quat_nlerp(a, b, t);
    }

    double theta = acos(dot);
    double sin_theta = sin(theta);
    double wa = sin((1 - t) * theta) / sin_theta;
    double wb = sin(t * theta) / sin_theta;

    return TC_QUAT(
        wa * a.x + wb * b.x,
        wa * a.y + wb * b.y,
        wa * a.z + wb * b.z,
        wa * a.w + wb * b.w
    );
}

// ============================================================================
// Conversion
// ============================================================================

// Extract Euler angles (XYZ order, radians)
static inline tc_vec3 tc_quat_to_euler(tc_quat q) {
    double sinr_cosp = 2.0 * (q.w * q.x + q.y * q.z);
    double cosr_cosp = 1.0 - 2.0 * (q.x * q.x + q.y * q.y);
    double x = atan2(sinr_cosp, cosr_cosp);

    double sinp = 2.0 * (q.w * q.y - q.z * q.x);
    double y;
    if (fabs(sinp) >= 1.0) {
        y = copysign(M_PI / 2, sinp);
    } else {
        y = asin(sinp);
    }

    double siny_cosp = 2.0 * (q.w * q.z + q.x * q.y);
    double cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z);
    double z = atan2(siny_cosp, cosy_cosp);

    return TC_VEC3(x, y, z);
}

#ifdef __cplusplus
}
#endif

#endif // TC_QUAT_H
