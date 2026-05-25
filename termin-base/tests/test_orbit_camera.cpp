#include <cmath>

#include <termin/camera/orbit_camera.hpp>

#include "guard_main.h"

namespace {

bool near(float a, float b, float eps = 1.0e-4f) {
    return std::abs(a - b) <= eps;
}

}  // namespace

TEST_CASE("OrbitCamera default eye matches tcplot convention") {
    termin::OrbitCamera camera;
    float eye[3];
    camera.compute_eye(eye);

    CHECK(near(eye[0], 3.061862f));
    CHECK(near(eye[1], -3.061862f));
    CHECK(near(eye[2], 2.5f));
}

TEST_CASE("OrbitCamera fit_bounds updates target and clip planes") {
    termin::OrbitCamera camera;
    const float lo[3] = {-1.0f, -2.0f, -3.0f};
    const float hi[3] = {3.0f, 4.0f, 5.0f};

    camera.fit_bounds(lo, hi);

    CHECK(near(camera.target.x, 1.0f));
    CHECK(near(camera.target.y, 1.0f));
    CHECK(near(camera.target.z, 1.0f));
    CHECK(camera.distance > 0.0f);
    CHECK(camera.near_clip >= 0.01f);
    CHECK(camera.far_clip > camera.near_clip);
}

TEST_CASE("OrbitCamera center screen ray points toward target") {
    termin::OrbitCamera camera;
    termin::OrbitCameraRay ray = camera.screen_ray(400.0f, 300.0f, 800.0f, 600.0f);
    termin::Vec3f to_target = (camera.target - ray.origin).normalized();

    CHECK(ray.direction.dot(to_target) > 0.999f);
}

GUARD_TEST_MAIN();
