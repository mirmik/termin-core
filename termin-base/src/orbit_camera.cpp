#include "termin/camera/orbit_camera.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace termin {
namespace {

constexpr float kPi = 3.14159265358979323846f;
constexpr float kDegToRad = kPi / 180.0f;
constexpr float kEpsilon = 1.0e-8f;

inline float& M(float* m, int col, int row) { return m[col * 4 + row]; }

void copy_mat(const Mat44f& src, float out16[16]) {
    std::memcpy(out16, src.data, sizeof(src.data));
}

Mat44f look_at_negative_z(const Vec3f& eye,
                          const Vec3f& target,
                          const Vec3f& up) {
    Vec3f f = (target - eye).normalized();
    Vec3f s = f.cross(up).normalized();
    Vec3f u = s.cross(f);

    Mat44f m = Mat44f::identity();
    m(0, 0) = s.x;   m(1, 0) = s.y;   m(2, 0) = s.z;
    m(0, 1) = u.x;   m(1, 1) = u.y;   m(2, 1) = u.z;
    m(0, 2) = -f.x;  m(1, 2) = -f.y;  m(2, 2) = -f.z;
    m(3, 0) = -s.dot(eye);
    m(3, 1) = -u.dot(eye);
    m(3, 2) = f.dot(eye);
    return m;
}

Mat44f perspective_negative_z(float fov_y, float aspect,
                              float near_clip, float far_clip) {
    Mat44f m;
    const float f = 1.0f / std::tan(fov_y * 0.5f);
    const float fn = far_clip - near_clip;
    m(0, 0) = f / aspect;
    m(1, 1) = -f;
    m(2, 2) = -far_clip / fn;
    m(3, 2) = -(far_clip * near_clip) / fn;
    m(2, 3) = -1.0f;
    return m;
}

Vec3f transform_clip_point(const Mat44f& m, float x, float y, float z) {
    const float tx = m(0, 0) * x + m(1, 0) * y + m(2, 0) * z + m(3, 0);
    const float ty = m(0, 1) * x + m(1, 1) * y + m(2, 1) * z + m(3, 1);
    const float tz = m(0, 2) * x + m(1, 2) * y + m(2, 2) * z + m(3, 2);
    const float tw = m(0, 3) * x + m(1, 3) * y + m(2, 3) * z + m(3, 3);
    if (std::abs(tw) <= kEpsilon) {
        return {tx, ty, tz};
    }
    return {tx / tw, ty / tw, tz / tw};
}

}  // namespace

OrbitCamera::OrbitCamera()
    : azimuth(45.0f * kDegToRad),
      elevation(30.0f * kDegToRad),
      fov_y(45.0f * kDegToRad),
      min_elevation(-89.0f * kDegToRad),
      max_elevation(89.0f * kDegToRad) {}

Vec3f OrbitCamera::eye() const {
    const float ce = std::cos(elevation);
    const float se = std::sin(elevation);
    const float ca = std::cos(azimuth);
    const float sa = std::sin(azimuth);
    return {
        target.x + distance * (ce * sa),
        target.y + distance * (-ce * ca),
        target.z + distance * se,
    };
}

void OrbitCamera::compute_eye(float out[3]) const {
    const Vec3f e = eye();
    out[0] = e.x;
    out[1] = e.y;
    out[2] = e.z;
}

Mat44f OrbitCamera::view_matrix() const {
    return look_at_negative_z(eye(), target, Vec3f::unit_z());
}

Mat44f OrbitCamera::projection_matrix(float aspect) const {
    return perspective_negative_z(fov_y, aspect, near_clip, far_clip);
}

Mat44f OrbitCamera::mvp(float aspect) const {
    return projection_matrix(aspect) * view_matrix();
}

void OrbitCamera::view_matrix(float out16[16]) const {
    copy_mat(view_matrix(), out16);
}

void OrbitCamera::projection_matrix(float aspect, float out16[16]) const {
    copy_mat(projection_matrix(aspect), out16);
}

void OrbitCamera::mvp(float aspect, float out16[16]) const {
    copy_mat(mvp(aspect), out16);
}

void OrbitCamera::orbit(float d_azimuth, float d_elevation) {
    azimuth += d_azimuth;
    elevation = std::clamp(elevation + d_elevation,
                           min_elevation, max_elevation);
}

void OrbitCamera::zoom(float factor) {
    distance = std::clamp(distance * factor, min_distance, max_distance);
    update_clip_planes();
}

void OrbitCamera::pan(float dx, float dy) {
    const float ce = std::cos(elevation);
    const float se = std::sin(elevation);
    const float ca = std::cos(azimuth);
    const float sa = std::sin(azimuth);

    const Vec3f right{ca, sa, 0.0f};
    const Vec3f forward{-ce * sa, ce * ca, -se};
    const Vec3f up = right.cross(forward).normalized();

    const float scale = distance * 0.002f;
    target += right * (dx * scale) + up * (dy * scale);
}

void OrbitCamera::fit_bounds(const Vec3f& bounds_min,
                             const Vec3f& bounds_max) {
    target = (bounds_min + bounds_max) * 0.5f;

    const Vec3f extent = bounds_max - bounds_min;
    const float size = extent.norm();

    fitted_radius = std::max(size * 0.5f, 1.0f);
    distance = std::max(size * 1.2f, min_distance);
    min_distance = std::max(fitted_radius * 0.001f, 0.01f);
    max_distance = std::max(max_distance, distance + fitted_radius * 20.0f);
    update_clip_planes();
}

void OrbitCamera::fit_bounds(const float bounds_min[3],
                             const float bounds_max[3]) {
    fit_bounds(Vec3f{bounds_min[0], bounds_min[1], bounds_min[2]},
               Vec3f{bounds_max[0], bounds_max[1], bounds_max[2]});
}

OrbitCameraRay OrbitCamera::screen_ray(float screen_x, float screen_y,
                                       float width, float height) const {
    const float safe_w = std::max(width, 1.0f);
    const float safe_h = std::max(height, 1.0f);
    const float aspect = std::max(safe_w / safe_h, 0.001f);
    const float ndc_x = screen_x / safe_w * 2.0f - 1.0f;
    const float ndc_y = screen_y / safe_h * 2.0f - 1.0f;

    const Mat44f inv_vp = mvp(aspect).inverse();
    const Vec3f near_p = transform_clip_point(inv_vp, ndc_x, ndc_y, 0.0f);
    const Vec3f far_p = transform_clip_point(inv_vp, ndc_x, ndc_y, 1.0f);
    return {near_p, (far_p - near_p).normalized()};
}

std::optional<Vec3f> OrbitCamera::world_point_on_z_plane(
        float screen_x, float screen_y,
        float width, float height,
        float z) const {
    const OrbitCameraRay ray = screen_ray(screen_x, screen_y, width, height);
    if (std::abs(ray.direction.z) < kEpsilon) {
        return std::nullopt;
    }
    const float t = (z - ray.origin.z) / ray.direction.z;
    if (t < 0.0f) {
        return std::nullopt;
    }
    return ray.origin + ray.direction * t;
}

void OrbitCamera::update_clip_planes() {
    const float radius = std::max(fitted_radius, 1.0f);
    const float margin = radius * 2.5f;
    near_clip = std::max(0.01f, distance - margin);
    far_clip = std::max(near_clip + 1.0f, distance + margin);
}

}  // namespace termin
