// tc_types.h - Basic types shared across Termin libraries
#ifndef TC_TYPES_H
#define TC_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
#include <cmath>
#endif

#include <tcbase/tc_binding_types.h>
#include <tcbase/tcbase_api.h>

// Backward-compatible export macro used by existing C APIs.
// Each library that exposes TC_API symbols defines TC_EXPORTS when building.
#ifndef TC_API
    #ifdef _WIN32
        #ifdef TC_EXPORTS
            #define TC_API __declspec(dllexport)
        #else
            #define TC_API __declspec(dllimport)
        #endif
    #else
        #define TC_API
    #endif
#endif

#ifdef __cplusplus

struct tc_vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;

    constexpr tc_vec3() noexcept = default;
    constexpr tc_vec3(double x, double y, double z) noexcept : x(x), y(y), z(z) {}

    double& operator[](int i) { return (&x)[i]; }
    double operator[](int i) const { return (&x)[i]; }

    tc_vec3 operator+(const tc_vec3& v) const { return {x + v.x, y + v.y, z + v.z}; }
    tc_vec3 operator-(const tc_vec3& v) const { return {x - v.x, y - v.y, z - v.z}; }
    tc_vec3 operator*(double s) const { return {x * s, y * s, z * s}; }
    tc_vec3 operator/(double s) const { return {x / s, y / s, z / s}; }
    tc_vec3 operator-() const { return {-x, -y, -z}; }

    tc_vec3& operator+=(const tc_vec3& v) { x += v.x; y += v.y; z += v.z; return *this; }
    tc_vec3& operator-=(const tc_vec3& v) { x -= v.x; y -= v.y; z -= v.z; return *this; }
    tc_vec3& operator*=(double s) { x *= s; y *= s; z *= s; return *this; }
    tc_vec3& operator/=(double s) { x /= s; y /= s; z /= s; return *this; }

    bool operator==(const tc_vec3& v) const { return x == v.x && y == v.y && z == v.z; }
    bool operator!=(const tc_vec3& v) const { return !(*this == v); }

    double dot(const tc_vec3& v) const { return x * v.x + y * v.y + z * v.z; }

    tc_vec3 cross(const tc_vec3& v) const {
        return {
            y * v.z - z * v.y,
            z * v.x - x * v.z,
            x * v.y - y * v.x
        };
    }

    double norm() const { return std::sqrt(x * x + y * y + z * z); }
    double norm_squared() const { return x * x + y * y + z * z; }

    tc_vec3 normalized() const {
        double n = norm();
        return n > 1e-10 ? *this / n : tc_vec3{0, 0, 1};
    }

    static double angle(const tc_vec3& a, const tc_vec3& b) {
        double d = a.normalized().dot(b.normalized());
        d = d < -1.0 ? -1.0 : (d > 1.0 ? 1.0 : d);
        return std::acos(d);
    }

    static double angle_degrees(const tc_vec3& a, const tc_vec3& b) {
        return angle(a, b) * 180.0 / 3.14159265358979323846;
    }

    static tc_vec3 zero() { return {0, 0, 0}; }
    static tc_vec3 unit_x() { return {1, 0, 0}; }
    static tc_vec3 unit_y() { return {0, 1, 0}; }
    static tc_vec3 unit_z() { return {0, 0, 1}; }
    static tc_vec3 right() { return unit_x(); }
    static tc_vec3 left() { return {-1, 0, 0}; }
    static tc_vec3 forward() { return unit_y(); }
    static tc_vec3 backward() { return {0, -1, 0}; }
    static tc_vec3 up() { return unit_z(); }
    static tc_vec3 down() { return {0, 0, -1}; }
};

extern "C++" {
inline tc_vec3 operator*(double s, const tc_vec3& v) { return v * s; }
}

struct tc_quat {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 1.0;

    constexpr tc_quat() noexcept = default;
    constexpr tc_quat(double x, double y, double z, double w) noexcept
        : x(x), y(y), z(z), w(w) {}

    static tc_quat identity() { return {0, 0, 0, 1}; }

    tc_quat operator*(const tc_quat& q) const {
        return {
            w * q.x + x * q.w + y * q.z - z * q.y,
            w * q.y - x * q.z + y * q.w + z * q.x,
            w * q.z + x * q.y - y * q.x + z * q.w,
            w * q.w - x * q.x - y * q.y - z * q.z
        };
    }

    tc_quat conjugate() const { return {-x, -y, -z, w}; }
    tc_quat inverse() const { return conjugate(); }

    double norm() const { return std::sqrt(x * x + y * y + z * z + w * w); }

    tc_quat normalized() const {
        double n = norm();
        return n > 1e-10 ? tc_quat{x / n, y / n, z / n, w / n} : identity();
    }

    tc_vec3 rotate(const tc_vec3& v) const {
        double tx = 2.0 * (y * v.z - z * v.y);
        double ty = 2.0 * (z * v.x - x * v.z);
        double tz = 2.0 * (x * v.y - y * v.x);

        return {
            v.x + w * tx + y * tz - z * ty,
            v.y + w * ty + z * tx - x * tz,
            v.z + w * tz + x * ty - y * tx
        };
    }

    tc_vec3 inverse_rotate(const tc_vec3& v) const {
        return conjugate().rotate(v);
    }

    static tc_quat from_axis_angle(const tc_vec3& axis, double angle) {
        double half = angle * 0.5;
        double s = std::sin(half);
        tc_vec3 n = axis.normalized();
        return {n.x * s, n.y * s, n.z * s, std::cos(half)};
    }

    static tc_quat look_rotation(const tc_vec3& forward, const tc_vec3& up = tc_vec3::unit_z()) {
        tc_vec3 f = forward.normalized();
        tc_vec3 r = f.cross(up).normalized();
        tc_vec3 u = r.cross(f);

        double m[9] = {
            r.x, f.x, u.x,
            r.y, f.y, u.y,
            r.z, f.z, u.z
        };
        return from_rotation_matrix(m);
    }

    static tc_quat slerp(const tc_quat& q1, tc_quat q2, double t) {
        double dot = q1.x * q2.x + q1.y * q2.y + q1.z * q2.z + q1.w * q2.w;

        if (dot < 0) {
            q2 = {-q2.x, -q2.y, -q2.z, -q2.w};
            dot = -dot;
        }

        if (dot > 0.9995) {
            tc_quat result = {
                q1.x + t * (q2.x - q1.x),
                q1.y + t * (q2.y - q1.y),
                q1.z + t * (q2.z - q1.z),
                q1.w + t * (q2.w - q1.w)
            };
            return result.normalized();
        }

        double theta_0 = std::acos(dot);
        double theta = theta_0 * t;
        double sin_theta = std::sin(theta);
        double sin_theta_0 = std::sin(theta_0);

        double s1 = std::cos(theta) - dot * sin_theta / sin_theta_0;
        double s2 = sin_theta / sin_theta_0;

        return {
            s1 * q1.x + s2 * q2.x,
            s1 * q1.y + s2 * q2.y,
            s1 * q1.z + s2 * q2.z,
            s1 * q1.w + s2 * q2.w
        };
    }

    static tc_quat from_rotation_matrix(const double* m) {
        double trace = m[0] + m[4] + m[8];
        double x, y, z, w;

        if (trace > 0) {
            double s = 0.5 / std::sqrt(trace + 1.0);
            w = 0.25 / s;
            x = (m[7] - m[5]) * s;
            y = (m[2] - m[6]) * s;
            z = (m[3] - m[1]) * s;
        } else if (m[0] > m[4] && m[0] > m[8]) {
            double s = 2.0 * std::sqrt(1.0 + m[0] - m[4] - m[8]);
            w = (m[7] - m[5]) / s;
            x = 0.25 * s;
            y = (m[1] + m[3]) / s;
            z = (m[2] + m[6]) / s;
        } else if (m[4] > m[8]) {
            double s = 2.0 * std::sqrt(1.0 + m[4] - m[0] - m[8]);
            w = (m[2] - m[6]) / s;
            x = (m[1] + m[3]) / s;
            y = 0.25 * s;
            z = (m[5] + m[7]) / s;
        } else {
            double s = 2.0 * std::sqrt(1.0 + m[8] - m[0] - m[4]);
            w = (m[3] - m[1]) / s;
            x = (m[2] + m[6]) / s;
            y = (m[5] + m[7]) / s;
            z = 0.25 * s;
        }

        return tc_quat{x, y, z, w}.normalized();
    }

    void to_matrix(double* m) const {
        double xx = x * x, yy = y * y, zz = z * z;
        double xy = x * y, xz = x * z, yz = y * z;
        double wx = w * x, wy = w * y, wz = w * z;

        m[0] = 1 - 2 * (yy + zz);  m[1] = 2 * (xy - wz);      m[2] = 2 * (xz + wy);
        m[3] = 2 * (xy + wz);      m[4] = 1 - 2 * (xx + zz);  m[5] = 2 * (yz - wx);
        m[6] = 2 * (xz - wy);      m[7] = 2 * (yz + wx);      m[8] = 1 - 2 * (xx + yy);
    }
};

struct tc_vec3f {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    constexpr tc_vec3f() noexcept = default;
    constexpr tc_vec3f(float x, float y, float z) noexcept : x(x), y(y), z(z) {}
    explicit tc_vec3f(const tc_vec3& v)
        : x(static_cast<float>(v.x))
        , y(static_cast<float>(v.y))
        , z(static_cast<float>(v.z)) {}

    float& operator[](int i) { return (&x)[i]; }
    float operator[](int i) const { return (&x)[i]; }

    tc_vec3f operator+(const tc_vec3f& v) const { return {x + v.x, y + v.y, z + v.z}; }
    tc_vec3f operator-(const tc_vec3f& v) const { return {x - v.x, y - v.y, z - v.z}; }
    tc_vec3f operator*(float s) const { return {x * s, y * s, z * s}; }
    tc_vec3f operator/(float s) const { return {x / s, y / s, z / s}; }
    tc_vec3f operator-() const { return {-x, -y, -z}; }

    tc_vec3f& operator+=(const tc_vec3f& v) { x += v.x; y += v.y; z += v.z; return *this; }
    tc_vec3f& operator-=(const tc_vec3f& v) { x -= v.x; y -= v.y; z -= v.z; return *this; }
    tc_vec3f& operator*=(float s) { x *= s; y *= s; z *= s; return *this; }
    tc_vec3f& operator/=(float s) { x /= s; y /= s; z /= s; return *this; }

    bool operator==(const tc_vec3f& v) const { return x == v.x && y == v.y && z == v.z; }
    bool operator!=(const tc_vec3f& v) const { return !(*this == v); }

    float dot(const tc_vec3f& v) const { return x * v.x + y * v.y + z * v.z; }

    tc_vec3f cross(const tc_vec3f& v) const {
        return {
            y * v.z - z * v.y,
            z * v.x - x * v.z,
            x * v.y - y * v.x
        };
    }

    float norm() const { return std::sqrt(x * x + y * y + z * z); }
    float norm_squared() const { return x * x + y * y + z * z; }

    tc_vec3f normalized() const {
        float n = norm();
        return n > 1e-6f ? *this / n : tc_vec3f{0, 0, 1};
    }

    tc_vec3 to_double() const { return {x, y, z}; }

    static tc_vec3f zero() { return {0, 0, 0}; }
    static tc_vec3f unit_x() { return {1, 0, 0}; }
    static tc_vec3f unit_y() { return {0, 1, 0}; }
    static tc_vec3f unit_z() { return {0, 0, 1}; }
    static tc_vec3f right() { return unit_x(); }
    static tc_vec3f left() { return {-1, 0, 0}; }
    static tc_vec3f forward() { return unit_y(); }
    static tc_vec3f backward() { return {0, -1, 0}; }
    static tc_vec3f up() { return unit_z(); }
    static tc_vec3f down() { return {0, 0, -1}; }
};

extern "C++" {
inline tc_vec3f operator*(float s, const tc_vec3f& v) { return v * s; }
}

struct tc_quatf {
    float x;
    float y;
    float z;
    float w;
};

struct tc_pose3 {
    tc_quat rotation;
    tc_vec3 position;
};

struct tc_general_pose3 {
    tc_quat rotation;
    tc_vec3 position;
    tc_vec3 scale;
};

struct tc_mat44 {
    double m[16];  // column-major (OpenGL convention)
};

struct tc_transform;
struct tc_entity;
struct tc_component;
struct tc_component_vtable;
struct tc_component_ref_vtable;
struct tc_drawable_vtable;
struct tc_input_vtable;
struct tc_scene;
struct tc_viewport;
struct tc_pipeline;

#else

typedef struct tc_vec3 {
    double x, y, z;
} tc_vec3;

typedef struct tc_quat {
    double x, y, z, w;
} tc_quat;

typedef struct tc_vec3f {
    float x, y, z;
} tc_vec3f;

typedef struct tc_quatf {
    float x, y, z, w;
} tc_quatf;

// Layout matches C++ Pose3/GeneralPose3 for zero-cost interop.
typedef struct tc_pose3 {
    tc_quat rotation;
    tc_vec3 position;
} tc_pose3;

typedef struct tc_general_pose3 {
    tc_quat rotation;
    tc_vec3 position;
    tc_vec3 scale;
} tc_general_pose3;

typedef struct tc_mat44 {
    double m[16];  // column-major (OpenGL convention)
} tc_mat44;

typedef struct tc_transform tc_transform;
typedef struct tc_entity tc_entity;
typedef struct tc_component tc_component;
typedef struct tc_component_vtable tc_component_vtable;
typedef struct tc_component_ref_vtable tc_component_ref_vtable;
typedef struct tc_drawable_vtable tc_drawable_vtable;
typedef struct tc_input_vtable tc_input_vtable;
typedef struct tc_scene tc_scene;
typedef struct tc_viewport tc_viewport;
typedef struct tc_pipeline tc_pipeline;

#endif

#endif // TC_TYPES_H
