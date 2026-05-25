#include "common.hpp"

#include <nanobind/stl/optional.h>
#include <nanobind/stl/tuple.h>

#include <termin/camera/orbit_camera.hpp>

namespace termin {
namespace {

nb::tuple vec3f_tuple(Vec3f v) {
    return nb::make_tuple(v.x, v.y, v.z);
}

nb::tuple mat44f_tuple(const Mat44f& m) {
    nb::list result;
    for (float v : m.data) {
        result.append(v);
    }
    return nb::tuple(result);
}

Vec3f tuple_to_vec3f(std::tuple<float, float, float> v) {
    return {std::get<0>(v), std::get<1>(v), std::get<2>(v)};
}

}  // namespace

void bind_orbit_camera(nb::module_& m) {
    nb::class_<OrbitCamera>(m, "OrbitCamera")
        .def(nb::init<>())
        .def_prop_rw("target",
            [](const OrbitCamera& c) {
                return vec3f_tuple(c.target);
            },
            [](OrbitCamera& c, std::tuple<float, float, float> target) {
                c.target = tuple_to_vec3f(target);
            })
        .def_rw("distance", &OrbitCamera::distance)
        .def_rw("azimuth", &OrbitCamera::azimuth)
        .def_rw("elevation", &OrbitCamera::elevation)
        .def_rw("fov_y", &OrbitCamera::fov_y)
        .def_rw("near", &OrbitCamera::near_clip)
        .def_rw("far", &OrbitCamera::far_clip)
        .def_rw("near_clip", &OrbitCamera::near_clip)
        .def_rw("far_clip", &OrbitCamera::far_clip)
        .def_rw("fitted_radius", &OrbitCamera::fitted_radius)
        .def_rw("min_distance", &OrbitCamera::min_distance)
        .def_rw("max_distance", &OrbitCamera::max_distance)
        .def_rw("min_elevation", &OrbitCamera::min_elevation)
        .def_rw("max_elevation", &OrbitCamera::max_elevation)
        .def_prop_ro("eye", [](const OrbitCamera& c) {
            return vec3f_tuple(c.eye());
        })
        .def("view_matrix", [](const OrbitCamera& c) {
            return mat44f_tuple(c.view_matrix());
        })
        .def("projection_matrix", [](const OrbitCamera& c, float aspect) {
            return mat44f_tuple(c.projection_matrix(aspect));
        }, nb::arg("aspect"))
        .def("mvp", [](const OrbitCamera& c, float aspect) {
            return mat44f_tuple(c.mvp(aspect));
        }, nb::arg("aspect"))
        .def("orbit", &OrbitCamera::orbit,
             nb::arg("d_azimuth"), nb::arg("d_elevation"))
        .def("zoom", &OrbitCamera::zoom, nb::arg("factor"))
        .def("pan", &OrbitCamera::pan, nb::arg("dx"), nb::arg("dy"))
        .def("fit_bounds",
             [](OrbitCamera& c,
                std::tuple<float, float, float> bounds_min,
                std::tuple<float, float, float> bounds_max) {
                 c.fit_bounds(tuple_to_vec3f(bounds_min),
                              tuple_to_vec3f(bounds_max));
             },
             nb::arg("bounds_min"), nb::arg("bounds_max"))
        .def("screen_ray",
             [](const OrbitCamera& c,
                float screen_x, float screen_y,
                float width, float height) {
                 OrbitCameraRay ray = c.screen_ray(
                     screen_x, screen_y, width, height);
                 return nb::make_tuple(vec3f_tuple(ray.origin),
                                       vec3f_tuple(ray.direction));
             },
             nb::arg("screen_x"), nb::arg("screen_y"),
             nb::arg("width"), nb::arg("height"))
        .def("world_point_on_z_plane",
             [](const OrbitCamera& c,
                float screen_x, float screen_y,
                float width, float height,
                float z) -> nb::object {
                 std::optional<Vec3f> p = c.world_point_on_z_plane(
                     screen_x, screen_y, width, height, z);
                 if (!p.has_value()) {
                     return nb::none();
                 }
                 return vec3f_tuple(*p);
             },
             nb::arg("screen_x"), nb::arg("screen_y"),
             nb::arg("width"), nb::arg("height"), nb::arg("z") = 0.0f);
}

}  // namespace termin
