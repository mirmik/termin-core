#include "common.hpp"

namespace termin {

void bind_pose3(nb::module_& m) {
    nb::class_<Pose3>(m, "Pose3")
        .def(nb::init<>())
        .def("__init__", [](Pose3* self, std::optional<Quat> ang,
                             std::optional<Vec3> lin) {
            new (self) Pose3{ang.value_or(Quat::identity()),
                              lin.value_or(Vec3::zero())};
        }, nb::arg("ang").none() = nb::none(), nb::arg("lin").none() = nb::none())
        // Convenience: Pose3(Vec3) - translation only
        .def("__init__", [](Pose3* self, const Vec3& lin) {
            new (self) Pose3{Quat::identity(), lin};
        })
        .def_prop_rw("ang",
            [](const Pose3& p) { return p.ang; },
            [](Pose3& p, const Quat& val) {
                p.ang = val;
            })
        .def_prop_rw("lin",
            [](const Pose3& p) { return p.lin; },
            [](Pose3& p, const Vec3& val) {
                p.lin = val;
            })
        .def(nb::self * nb::self)
        .def("__matmul__", [](const Pose3& a, const Pose3& b) { return a * b; })
        .def("inverse", &Pose3::inverse)
        .def("transform_point", nb::overload_cast<const Vec3&>(&Pose3::transform_point, nb::const_))
        .def("transform_vector", nb::overload_cast<const Vec3&>(&Pose3::transform_vector, nb::const_))
        .def("rotate_point", &Pose3::rotate_point)
        .def("inverse_transform_point", nb::overload_cast<const Vec3&>(&Pose3::inverse_transform_point, nb::const_))
        .def("inverse_transform_vector", nb::overload_cast<const Vec3&>(&Pose3::inverse_transform_vector, nb::const_))
        .def("point_to_global", nb::overload_cast<const Vec3&>(&Pose3::point_to_global, nb::const_))
        .def("vector_to_global", nb::overload_cast<const Vec3&>(&Pose3::vector_to_global, nb::const_))
        .def("point_to_local", nb::overload_cast<const Vec3&>(&Pose3::point_to_local, nb::const_))
        .def("vector_to_local", nb::overload_cast<const Vec3&>(&Pose3::vector_to_local, nb::const_))
        .def("forward_in_global", &Pose3::forward_in_global, nb::arg("distance") = 1.0)
        .def("backward_in_global", &Pose3::backward_in_global, nb::arg("distance") = 1.0)
        .def("up_in_global", &Pose3::up_in_global, nb::arg("distance") = 1.0)
        .def("down_in_global", &Pose3::down_in_global, nb::arg("distance") = 1.0)
        .def("right_in_global", &Pose3::right_in_global, nb::arg("distance") = 1.0)
        .def("left_in_global", &Pose3::left_in_global, nb::arg("distance") = 1.0)
        .def("global_forward_in_local", &Pose3::global_forward_in_local, nb::arg("distance") = 1.0)
        .def("global_backward_in_local", &Pose3::global_backward_in_local, nb::arg("distance") = 1.0)
        .def("global_up_in_local", &Pose3::global_up_in_local, nb::arg("distance") = 1.0)
        .def("global_down_in_local", &Pose3::global_down_in_local, nb::arg("distance") = 1.0)
        .def("global_right_in_local", &Pose3::global_right_in_local, nb::arg("distance") = 1.0)
        .def("global_left_in_local", &Pose3::global_left_in_local, nb::arg("distance") = 1.0)
        // rotate_vector is an alias for transform_vector (for Pose3 without scale, they are the same)
        .def("rotate_vector", nb::overload_cast<const Vec3&>(&Pose3::transform_vector, nb::const_))
        .def("inverse_rotate_vector", nb::overload_cast<const Vec3&>(&Pose3::inverse_transform_vector, nb::const_))
        .def("normalized", &Pose3::normalized)
        .def("with_translation", nb::overload_cast<const Vec3&>(&Pose3::with_translation, nb::const_))
        .def("with_rotation", &Pose3::with_rotation)
        .def("rotation_matrix", [](const Pose3& p) {
            double data[9];
            p.rotation_matrix(data);
            return mat33_row_tuple(data);
        })
        .def("rotation_mat33", [](const Pose3& p) {
            double data[9];
            p.rotation_matrix(data);
            Mat33 mat;
            for (int row = 0; row < 3; ++row)
                for (int col = 0; col < 3; ++col)
                    mat(col, row) = data[row * 3 + col];
            return mat;
        })
        .def_static("identity", &Pose3::identity)
        .def_static("translation", nb::overload_cast<double, double, double>(&Pose3::translation))
        .def_static("rotation", nb::overload_cast<const Vec3&, double>(&Pose3::rotation))
        .def_static("rotate_x", &Pose3::rotate_x)
        .def_static("rotate_y", &Pose3::rotate_y)
        .def_static("rotate_z", &Pose3::rotate_z)
        // Python-style aliases (rotateX instead of rotate_x)
        .def_static("rotateX", &Pose3::rotate_x)
        .def_static("rotateY", &Pose3::rotate_y)
        .def_static("rotateZ", &Pose3::rotate_z)
        // moveX, moveY, moveZ for translation
        .def_static("moveX", [](double d) { return Pose3::translation(d, 0, 0); })
        .def_static("moveY", [](double d) { return Pose3::translation(0, d, 0); })
        .def_static("moveZ", [](double d) { return Pose3::translation(0, 0, d); })
        .def_static("looking_at", [](const Vec3& eye, const Vec3& target,
                                      std::optional<Vec3> up) {
            return Pose3::looking_at(eye, target, up.value_or(Vec3::unit_z()));
        }, nb::arg("eye"), nb::arg("target"), nb::arg("up").none() = nb::none())
        .def_static("from_euler", &Pose3::from_euler,
                    nb::arg("roll"), nb::arg("pitch"), nb::arg("yaw"))
        .def("to_euler", nb::overload_cast<>(&Pose3::to_euler, nb::const_))
        .def("to_axis_angle", [](const Pose3& p) {
            Vec3 axis;
            double angle;
            p.to_axis_angle(axis, angle);
            return nb::make_tuple(axis, angle);
        })
        .def("distance", &Pose3::distance)
        .def("copy", &Pose3::copy)
        .def("as_matrix", [](const Pose3& p) {
            double data[16];
            double m[16];
            p.as_matrix(m);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    data[i * 4 + j] = m[j * 4 + i];  // column-major to row-major
            return mat44_row_tuple(data);
        })
        .def("as_mat44", [](const Pose3& p) {
            Mat44 mat;
            p.as_matrix(mat.data);
            return mat;
        })
        .def("as_matrix34", [](const Pose3& p) {
            double data[12];
            double rot[9];
            p.rotation_matrix(rot);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    data[i * 4 + j] = rot[i * 3 + j];
            data[3] = p.lin.x;
            data[7] = p.lin.y;
            data[11] = p.lin.z;
            return mat34_row_tuple(data);
        })
        .def("compose", [](const Pose3& a, const Pose3& b) { return a * b; })
        // x, y, z property shortcuts for translation
        .def_prop_rw("x",
            [](const Pose3& p) { return p.lin.x; },
            [](Pose3& p, double v) { p.lin.x = v; })
        .def_prop_rw("y",
            [](const Pose3& p) { return p.lin.y; },
            [](Pose3& p, double v) { p.lin.y = v; })
        .def_prop_rw("z",
            [](const Pose3& p) { return p.lin.z; },
            [](Pose3& p, double v) { p.lin.z = v; })
        // Static translation methods (aliases)
        .def_static("right", [](double d) { return Pose3::translation(d, 0, 0); })
        .def_static("forward", [](double d) { return Pose3::translation(0, d, 0); })
        .def_static("up", [](double d) { return Pose3::translation(0, 0, d); })
        // Static from_axis_angle
        .def_static("from_axis_angle", [](const Vec3& axis, double angle) {
            return Pose3::rotation(axis, angle);
        })
        // Static lerp
        .def_static("lerp", [](const Pose3& a, const Pose3& b, double t) {
            return lerp(a, b, t);
        })
        .def("to_general_pose3", [](const Pose3& p, std::optional<Vec3> scale) {
            return GeneralPose3(p.ang, p.lin,
                                scale.value_or(Vec3{1.0, 1.0, 1.0}));
        }, nb::arg("scale").none() = nb::none())
        .def("__repr__", [](const Pose3& p) {
            return "Pose3(ang=Quat(" + std::to_string(p.ang.x) + ", " +
                   std::to_string(p.ang.y) + ", " + std::to_string(p.ang.z) + ", " +
                   std::to_string(p.ang.w) + "), lin=Vec3(" +
                   std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " +
                   std::to_string(p.lin.z) + "))";
        });

    m.def("lerp",
          static_cast<Pose3 (*)(const Pose3&, const Pose3&, double)>(&lerp),
          "Linear interpolation between poses");
}

} // namespace termin
