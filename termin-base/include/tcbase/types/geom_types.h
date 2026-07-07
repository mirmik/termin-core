// tcbase/types/geom_types.h - ABI-friendly geometry POD types
#ifndef TCBASE_TYPES_GEOM_TYPES_H
#define TCBASE_TYPES_GEOM_TYPES_H

#include <stddef.h>

#ifdef __cplusplus
#include <cmath>
#include <limits>

namespace termin {
struct Mat44;
}
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
        double nan = std::numeric_limits<double>::quiet_NaN();
        return n > 1e-10 ? *this / n : tc_vec3{nan, nan, nan};
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

struct tc_ray3 {
    tc_vec3 origin;
    tc_vec3 direction;

    constexpr tc_ray3() noexcept
        : origin(0.0, 0.0, 0.0)
        , direction(0.0, 0.0, 1.0) {}

    tc_ray3(const tc_vec3& origin, const tc_vec3& dir)
        : origin(origin) {
        double n = dir.norm();
        direction = (n > 1e-10) ? dir / n : tc_vec3{0.0, 0.0, 1.0};
    }

    tc_vec3 point_at(double t) const {
        return origin + direction * t;
    }
};

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
    tc_quat ang;
    tc_vec3 lin;

    constexpr tc_pose3() noexcept = default;
    constexpr tc_pose3(const tc_quat& ang, const tc_vec3& lin) noexcept
        : ang(ang), lin(lin) {}

    static tc_pose3 identity();

    tc_pose3 operator*(const tc_pose3& other) const;
    tc_pose3 inverse() const;

    tc_vec3 transform_point(const tc_vec3& p) const;
    tc_vec3 transform_vector(const tc_vec3& v) const;
    tc_vec3 rotate_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_vector(const tc_vec3& v) const;

    tc_vec3 point_to_global(const tc_vec3& p) const;
    tc_vec3 vector_to_global(const tc_vec3& v) const;
    tc_vec3 point_to_local(const tc_vec3& p) const;
    tc_vec3 vector_to_local(const tc_vec3& v) const;

    tc_vec3 forward_in_global(double distance = 1.0) const;
    tc_vec3 backward_in_global(double distance = 1.0) const;
    tc_vec3 up_in_global(double distance = 1.0) const;
    tc_vec3 down_in_global(double distance = 1.0) const;
    tc_vec3 right_in_global(double distance = 1.0) const;
    tc_vec3 left_in_global(double distance = 1.0) const;

    tc_vec3 global_forward_in_local(double distance = 1.0) const;
    tc_vec3 global_backward_in_local(double distance = 1.0) const;
    tc_vec3 global_up_in_local(double distance = 1.0) const;
    tc_vec3 global_down_in_local(double distance = 1.0) const;
    tc_vec3 global_right_in_local(double distance = 1.0) const;
    tc_vec3 global_left_in_local(double distance = 1.0) const;

    tc_pose3 normalized() const;
    tc_pose3 with_translation(const tc_vec3& new_lin) const;
    tc_pose3 with_rotation(const tc_quat& new_ang) const;

    void rotation_matrix(double* m) const;
    void as_matrix(double* m) const;
    termin::Mat44 as_mat44() const;

    double distance(const tc_pose3& other) const;

    static tc_pose3 translation(double x, double y, double z);
    static tc_pose3 translation(const tc_vec3& t);
    static tc_pose3 rotation(const tc_vec3& axis, double angle);
    static tc_pose3 rotate_x(double angle);
    static tc_pose3 rotate_y(double angle);
    static tc_pose3 rotate_z(double angle);
    static tc_pose3 looking_at(
        const tc_vec3& eye,
        const tc_vec3& target,
        const tc_vec3& up = tc_vec3::unit_z());
    static tc_pose3 from_euler(double roll, double pitch, double yaw);

    tc_vec3 to_euler() const;
    void to_axis_angle(tc_vec3& axis, double& angle) const;
    tc_pose3 copy() const;
};

struct tc_general_pose3 {
    tc_quat ang;
    tc_vec3 lin;
    tc_vec3 scale = {1.0, 1.0, 1.0};

    constexpr tc_general_pose3() noexcept = default;
    constexpr tc_general_pose3(
        const tc_quat& ang,
        const tc_vec3& lin,
        const tc_vec3& scale = tc_vec3{1.0, 1.0, 1.0}) noexcept
        : ang(ang), lin(lin), scale(scale) {}

    static tc_general_pose3 identity();

    tc_general_pose3 operator*(const tc_general_pose3& other) const;
    tc_general_pose3 operator*(const tc_pose3& other) const;
    tc_general_pose3 inverse() const;

    tc_vec3 transform_point(const tc_vec3& p) const;
    tc_vec3 transform_vector(const tc_vec3& v) const;
    tc_vec3 transform_direction(const tc_vec3& d) const;
    tc_vec3 rotate_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_vector(const tc_vec3& v) const;
    tc_vec3 inverse_transform_direction(const tc_vec3& d) const;

    tc_vec3 point_to_global(const tc_vec3& p) const;
    tc_vec3 vector_to_global(const tc_vec3& v) const;
    tc_vec3 direction_to_global(const tc_vec3& d) const;
    tc_vec3 point_to_local(const tc_vec3& p) const;
    tc_vec3 vector_to_local(const tc_vec3& v) const;
    tc_vec3 direction_to_local(const tc_vec3& d) const;

    tc_vec3 forward_in_global(double distance = 1.0) const;
    tc_vec3 backward_in_global(double distance = 1.0) const;
    tc_vec3 up_in_global(double distance = 1.0) const;
    tc_vec3 down_in_global(double distance = 1.0) const;
    tc_vec3 right_in_global(double distance = 1.0) const;
    tc_vec3 left_in_global(double distance = 1.0) const;

    tc_vec3 global_forward_in_local(double distance = 1.0) const;
    tc_vec3 global_backward_in_local(double distance = 1.0) const;
    tc_vec3 global_up_in_local(double distance = 1.0) const;
    tc_vec3 global_down_in_local(double distance = 1.0) const;
    tc_vec3 global_right_in_local(double distance = 1.0) const;
    tc_vec3 global_left_in_local(double distance = 1.0) const;

    tc_general_pose3 normalized() const;
    tc_general_pose3 with_rotation(const tc_quat& new_ang) const;
    tc_general_pose3 with_translation(const tc_vec3& new_lin) const;
    tc_general_pose3 with_scale(const tc_vec3& new_scale) const;
    tc_pose3 to_pose3() const;

    void rotation_matrix(double* m) const;
    void matrix4(double* m) const;
    void matrix34(double* m) const;
    void inverse_matrix4(double* m) const;

    double distance(const tc_general_pose3& other) const;

    static tc_general_pose3 translation(double x, double y, double z);
    static tc_general_pose3 translation(const tc_vec3& t);
    static tc_general_pose3 rotation(const tc_vec3& axis, double angle);
    static tc_general_pose3 scaling(double sx, double sy, double sz);
    static tc_general_pose3 scaling(double s);
    static tc_general_pose3 rotate_x(double angle);
    static tc_general_pose3 rotate_y(double angle);
    static tc_general_pose3 rotate_z(double angle);
    static tc_general_pose3 move(double dx, double dy, double dz);
    static tc_general_pose3 move_x(double d);
    static tc_general_pose3 move_y(double d);
    static tc_general_pose3 move_z(double d);
    static tc_general_pose3 right(double d);
    static tc_general_pose3 forward(double d);
    static tc_general_pose3 up(double d);
    static tc_general_pose3 looking_at(
        const tc_vec3& eye,
        const tc_vec3& target,
        const tc_vec3& up_vec = tc_vec3{0.0, 0.0, 1.0});
};

struct tc_screw3 {
    tc_vec3 ang;
    tc_vec3 lin;

    constexpr tc_screw3() noexcept = default;
    constexpr tc_screw3(const tc_vec3& ang, const tc_vec3& lin) noexcept
        : ang(ang), lin(lin) {}

    static tc_screw3 zero();

    tc_screw3 operator+(const tc_screw3& s) const;
    tc_screw3 operator-(const tc_screw3& s) const;
    tc_screw3 operator*(double k) const;
    tc_screw3 operator-() const;

    tc_screw3& operator+=(const tc_screw3& s);
    tc_screw3& operator-=(const tc_screw3& s);
    tc_screw3& operator*=(double k);

    tc_screw3 scaled(double k) const;
    double dot(const tc_screw3& s) const;
    tc_screw3 cross_motion(const tc_screw3& s) const;
    tc_screw3 cross_force(const tc_screw3& s) const;
    tc_screw3 transform_by(const tc_pose3& pose) const;
    tc_screw3 inverse_transform_by(const tc_pose3& pose) const;
    tc_screw3 adjoint(const tc_pose3& pose) const;
    tc_screw3 adjoint(const tc_vec3& arm) const;
    tc_screw3 adjoint_inv(const tc_pose3& pose) const;
    tc_screw3 adjoint_inv(const tc_vec3& arm) const;
    tc_screw3 coadjoint(const tc_pose3& pose) const;
    tc_screw3 coadjoint(const tc_vec3& arm) const;
    tc_screw3 coadjoint_inv(const tc_pose3& pose) const;
    tc_screw3 coadjoint_inv(const tc_vec3& arm) const;
    tc_pose3 to_pose() const;
};

extern "C++" {
inline tc_screw3 operator*(double k, const tc_screw3& s) { return s * k; }
}

struct tc_aabb {
    tc_vec3 min_point;
    tc_vec3 max_point;

    constexpr tc_aabb() noexcept = default;
    constexpr tc_aabb(const tc_vec3& min_pt, const tc_vec3& max_pt) noexcept
        : min_point(min_pt), max_point(max_pt) {}

    void extend(const tc_vec3& point);
    bool intersects(const tc_aabb& other) const;
    bool contains(const tc_vec3& point) const;
    tc_aabb merge(const tc_aabb& other) const;
    tc_vec3 center() const;
    tc_vec3 size() const;
    tc_vec3 half_size() const;
    tc_vec3 project_point(const tc_vec3& point) const;
    double surface_area() const;
    double volume() const;
    static tc_aabb from_points(const tc_vec3* points, size_t count);

    tc_aabb transformed_by(const tc_pose3& pose) const;
    tc_aabb transformed_by(const tc_general_pose3& pose) const;
    void get_corners(tc_vec3* out_corners) const;
};

struct tc_mat44 {
    double m[16];  // column-major (OpenGL convention)
};

#else

typedef struct tc_vec3 {
    double x, y, z;
} tc_vec3;

typedef struct tc_ray3 {
    tc_vec3 origin;
    tc_vec3 direction;
} tc_ray3;

typedef struct tc_quat {
    double x, y, z, w;
} tc_quat;

typedef struct tc_vec3f {
    float x, y, z;
} tc_vec3f;

typedef struct tc_quatf {
    float x, y, z, w;
} tc_quatf;

typedef struct tc_pose3 {
    tc_quat ang;
    tc_vec3 lin;
} tc_pose3;

typedef struct tc_general_pose3 {
    tc_quat ang;
    tc_vec3 lin;
    tc_vec3 scale;
} tc_general_pose3;

typedef struct tc_screw3 {
    tc_vec3 ang;
    tc_vec3 lin;
} tc_screw3;

typedef struct tc_aabb {
    tc_vec3 min_point;
    tc_vec3 max_point;
} tc_aabb;

typedef struct tc_mat44 {
    double m[16];  // column-major (OpenGL convention)
} tc_mat44;

#endif

#endif // TCBASE_TYPES_GEOM_TYPES_H
