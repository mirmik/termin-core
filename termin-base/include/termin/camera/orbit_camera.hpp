#pragma once

#include <optional>

#include <tcbase/tcbase_api.h>
#include <termin/geom/mat44.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/vec3.hpp>

namespace termin {

struct OrbitCameraRay {
    Vec3f origin;
    Vec3f direction;
};

class TCBASE_API OrbitCamera {
public:
    Vec3f target{0.0f, 0.0f, 0.0f};
    float distance = 5.0f;
    float azimuth;
    float elevation;
    float fov_y;
    float near_clip = 0.01f;
    float far_clip = 1000.0f;
    float fitted_radius = 1.0f;

    float min_distance = 0.01f;
    float max_distance = 10000.0f;
    float min_elevation;
    float max_elevation;

    OrbitCamera();

    Vec3f eye() const;
    void compute_eye(float out[3]) const;

    Mat44f view_matrix() const;
    Mat44f projection_matrix(float aspect) const;
    Mat44f mvp(float aspect) const;

    void view_matrix(float out16[16]) const;
    void projection_matrix(float aspect, float out16[16]) const;
    void mvp(float aspect, float out16[16]) const;

    void orbit(float d_azimuth, float d_elevation);
    void zoom(float factor);
    void pan(float dx, float dy);
    void fit_bounds(const Vec3f& bounds_min, const Vec3f& bounds_max);
    void fit_bounds(const float bounds_min[3], const float bounds_max[3]);

    OrbitCameraRay screen_ray(float screen_x, float screen_y,
                              float width, float height) const;
    std::optional<Vec3f> world_point_on_z_plane(float screen_x, float screen_y,
                                                float width, float height,
                                                float z = 0.0f) const;

private:
    void update_clip_planes();
};

}  // namespace termin
