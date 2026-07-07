#include "common.hpp"

#include <cmath>

namespace termin {

namespace {

nb::tuple vec2_tuple(const Vec2& v) {
    return nb::make_tuple(v.x, v.y);
}

} // namespace

void bind_pose2(nb::module_& m) {
    nb::class_<Pose2>(m, "Pose2")
        .def(nb::init<>())
        .def(nb::init<double, const Vec2&>(), nb::arg("ang") = 0.0, nb::arg("lin") = Vec2::zero())
        .def_rw("ang", &Pose2::ang)
        .def_prop_rw("lin",
            [](const Pose2& p) { return p.lin; },
            [](Pose2& p, const Vec2& lin) { p.lin = lin; })
        .def_prop_rw("x",
            [](const Pose2& p) { return p.lin.x; },
            [](Pose2& p, double x) { p.lin.x = x; })
        .def_prop_rw("y",
            [](const Pose2& p) { return p.lin.y; },
            [](Pose2& p, double y) { p.lin.y = y; })
        .def(nb::self * nb::self)
        .def("__matmul__", [](const Pose2& a, const Pose2& b) { return a * b; })
        .def("compose", [](const Pose2& a, const Pose2& b) { return a * b; })
        .def("copy", &Pose2::copy)
        .def("inverse", &Pose2::inverse)
        .def("transform_point", [](const Pose2& p, const Vec2& point) {
            return p.transform_point(point);
        })
        .def("transform_vector", [](const Pose2& p, const Vec2& vec) {
            return p.transform_vector(vec);
        })
        .def("rotate_vector", [](const Pose2& p, const Vec2& vec) {
            return p.rotate_vector(vec);
        })
        .def("inverse_transform_point", [](const Pose2& p, const Vec2& point) {
            return p.inverse_transform_point(point);
        })
        .def("inverse_rotate_vector", [](const Pose2& p, const Vec2& vec) {
            return p.inverse_rotate_vector(vec);
        })
        .def("inverse_transform_vector", [](const Pose2& p, const Vec2& vec) {
            return p.inverse_transform_vector(vec);
        })
        .def("rotation_matrix", [](const Pose2& p) {
            double c = std::cos(p.ang);
            double s = std::sin(p.ang);
            return nb::make_tuple(
                nb::make_tuple(c, -s),
                nb::make_tuple(s, c)
            );
        })
        .def("as_matrix", [](const Pose2& p) {
            double c = std::cos(p.ang);
            double s = std::sin(p.ang);
            return nb::make_tuple(
                nb::make_tuple(c, -s, p.lin.x),
                nb::make_tuple(s, c, p.lin.y),
                nb::make_tuple(0.0, 0.0, 1.0)
            );
        })
        .def("normalize_angle", &Pose2::normalize_angle)
        .def_static("identity", &Pose2::identity)
        .def_static("rotation", &Pose2::rotation)
        .def_static("translation", &Pose2::translation)
        .def_static("move", &Pose2::move)
        .def_static("moveX", &Pose2::move_x)
        .def_static("moveY", &Pose2::move_y)
        .def_static("right", &Pose2::right)
        .def_static("forward", &Pose2::forward)
        .def_static("lerp", &Pose2::lerp)
        .def("tolist", [](const Pose2& p) {
            return nb::make_tuple(p.ang, vec2_tuple(p.lin));
        })
        .def("__repr__", [](const Pose2& p) {
            return "Pose2(ang=" + std::to_string(p.ang) + ", lin=Vec2(" +
                   std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + "))";
        });
}

} // namespace termin
