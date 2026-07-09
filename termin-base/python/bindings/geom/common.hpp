#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/operators.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>

#include <termin/geom/geom.hpp>

namespace nb = nanobind;

namespace termin {

inline Vec3 sequence_to_vec3(nb::handle obj) {
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return Vec3{
        nb::cast<double>(seq[0]),
        nb::cast<double>(seq[1]),
        nb::cast<double>(seq[2]),
    };
}

inline Vec3f sequence_to_vec3f(nb::handle obj) {
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return Vec3f{
        nb::cast<float>(seq[0]),
        nb::cast<float>(seq[1]),
        nb::cast<float>(seq[2]),
    };
}

inline Quat sequence_to_quat(nb::handle obj) {
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return Quat{
        nb::cast<double>(seq[0]),
        nb::cast<double>(seq[1]),
        nb::cast<double>(seq[2]),
        nb::cast<double>(seq[3]),
    };
}

inline Vec4 sequence_to_vec4(nb::handle obj) {
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return Vec4{
        nb::cast<double>(seq[0]),
        nb::cast<double>(seq[1]),
        nb::cast<double>(seq[2]),
        nb::cast<double>(seq[3]),
    };
}

inline nb::tuple vec3_tuple(const Vec3& v) {
    return nb::make_tuple(v.x, v.y, v.z);
}

inline nb::tuple quat_tuple(const Quat& q) {
    return nb::make_tuple(q.x, q.y, q.z, q.w);
}

inline nb::tuple mat33_row_tuple(const double* data) {
    return nb::make_tuple(
        nb::make_tuple(data[0], data[1], data[2]),
        nb::make_tuple(data[3], data[4], data[5]),
        nb::make_tuple(data[6], data[7], data[8])
    );
}

inline nb::tuple mat34_row_tuple(const double* data) {
    return nb::make_tuple(
        nb::make_tuple(data[0], data[1], data[2], data[3]),
        nb::make_tuple(data[4], data[5], data[6], data[7]),
        nb::make_tuple(data[8], data[9], data[10], data[11])
    );
}

inline nb::tuple mat44_row_tuple(const double* data) {
    return nb::make_tuple(
        nb::make_tuple(data[0], data[1], data[2], data[3]),
        nb::make_tuple(data[4], data[5], data[6], data[7]),
        nb::make_tuple(data[8], data[9], data[10], data[11]),
        nb::make_tuple(data[12], data[13], data[14], data[15])
    );
}

// Forward declarations for binding functions
void bind_vec2(nb::module_& m);
void bind_pose2(nb::module_& m);
void bind_vec3(nb::module_& m);
void bind_vec4(nb::module_& m);
void bind_bounds2(nb::module_& m);
void bind_quat(nb::module_& m);
void bind_mat33(nb::module_& m);
void bind_mat44(nb::module_& m);
void bind_pose3(nb::module_& m);
void bind_general_pose3(nb::module_& m);
void bind_screw2(nb::module_& m);
void bind_screw3(nb::module_& m);
void bind_ray3(nb::module_& m);
void bind_aabb(nb::module_& m);
void bind_orbit_camera(nb::module_& m);

} // namespace termin
