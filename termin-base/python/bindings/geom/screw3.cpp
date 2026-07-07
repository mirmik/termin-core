#include "common.hpp"

namespace termin {

void bind_screw3(nb::module_& m) {
    nb::class_<Screw3>(m, "Screw3")
        .def(nb::init<>())
        .def(nb::init<const Vec3&, const Vec3&>(), nb::arg("ang"), nb::arg("lin"))
        .def_rw("ang", &Screw3::ang)
        .def_rw("lin", &Screw3::lin)
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * double())
        .def(double() * nb::self)
        .def(-nb::self)
        .def("dot", &Screw3::dot)
        .def("cross_motion", &Screw3::cross_motion)
        .def("cross_force", &Screw3::cross_force)
        .def("transform_by", &Screw3::transform_by)
        .def("inverse_transform_by", &Screw3::inverse_transform_by)
        .def("to_pose", &Screw3::to_pose)
        .def("as_pose3", &Screw3::to_pose)  // alias for compatibility
        .def("rotate_by", &Screw3::transform_by)
        .def("inverse_rotate_by", &Screw3::inverse_transform_by)
        .def("transform_as_twist_by", nb::overload_cast<const Pose3&>(&Screw3::adjoint, nb::const_))
        .def("inverse_transform_as_twist_by", nb::overload_cast<const Pose3&>(&Screw3::adjoint_inv, nb::const_))
        .def("transform_as_wrench_by", nb::overload_cast<const Pose3&>(&Screw3::coadjoint, nb::const_))
        .def("inverse_transform_as_wrench_by", nb::overload_cast<const Pose3&>(&Screw3::coadjoint_inv, nb::const_))
        .def("scaled", &Screw3::scaled)
        .def("moment", [](const Screw3& s) { return s.ang; })
        .def("vector", [](const Screw3& s) { return s.lin; })
        .def("copy", [](const Screw3& s) { return s; })
        .def("to_vector_vw_order", [](const Screw3& s) {
            return nb::make_tuple(s.lin.x, s.lin.y, s.lin.z, s.ang.x, s.ang.y, s.ang.z);
        })
        .def("to_vector_wv_order", [](const Screw3& s) {
            return nb::make_tuple(s.ang.x, s.ang.y, s.ang.z, s.lin.x, s.lin.y, s.lin.z);
        })
        .def("to_vw_array", [](const Screw3& s) {
            return nb::make_tuple(s.lin.x, s.lin.y, s.lin.z, s.ang.x, s.ang.y, s.ang.z);
        })
        .def("to_wv_array", [](const Screw3& s) {
            return nb::make_tuple(s.ang.x, s.ang.y, s.ang.z, s.lin.x, s.lin.y, s.lin.z);
        })
        // Adjoint overloads
        .def("adjoint", nb::overload_cast<const Pose3&>(&Screw3::adjoint, nb::const_))
        .def("adjoint", nb::overload_cast<const Vec3&>(&Screw3::adjoint, nb::const_))
        .def("adjoint_inv", nb::overload_cast<const Pose3&>(&Screw3::adjoint_inv, nb::const_))
        .def("adjoint_inv", nb::overload_cast<const Vec3&>(&Screw3::adjoint_inv, nb::const_))
        .def("coadjoint", nb::overload_cast<const Pose3&>(&Screw3::coadjoint, nb::const_))
        .def("coadjoint", nb::overload_cast<const Vec3&>(&Screw3::coadjoint, nb::const_))
        .def("coadjoint_inv", nb::overload_cast<const Pose3&>(&Screw3::coadjoint_inv, nb::const_))
        .def("coadjoint_inv", nb::overload_cast<const Vec3&>(&Screw3::coadjoint_inv, nb::const_))
        // Aliases for compatibility
        .def("kinematic_carry", nb::overload_cast<const Vec3&>(&Screw3::adjoint, nb::const_))
        .def("twist_carry", nb::overload_cast<const Vec3&>(&Screw3::adjoint, nb::const_))
        .def("force_carry", nb::overload_cast<const Vec3&>(&Screw3::coadjoint, nb::const_))
        .def("wrench_carry", nb::overload_cast<const Vec3&>(&Screw3::coadjoint, nb::const_))
        .def_static("zero", &Screw3::zero)
        .def_static("from_vector_vw_order", [](nb::sequence seq) {
            if (nb::len(seq) != 6) {
                throw nb::value_error("Input vector must be of shape (6,)");
            }
            return Screw3(
                Vec3(nb::cast<double>(seq[3]), nb::cast<double>(seq[4]), nb::cast<double>(seq[5])),
                Vec3(nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2]))
            );
        })
        .def_static("from_vector_wv_order", [](nb::sequence seq) {
            if (nb::len(seq) != 6) {
                throw nb::value_error("Input vector must be of shape (6,)");
            }
            return Screw3(
                Vec3(nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2])),
                Vec3(nb::cast<double>(seq[3]), nb::cast<double>(seq[4]), nb::cast<double>(seq[5]))
            );
        })
        .def_static("from_vw_array", [](nb::sequence seq) {
            if (nb::len(seq) != 6) {
                throw nb::value_error("Input vector must be of shape (6,)");
            }
            return Screw3(
                Vec3(nb::cast<double>(seq[3]), nb::cast<double>(seq[4]), nb::cast<double>(seq[5])),
                Vec3(nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2]))
            );
        })
        .def_static("from_wv_array", [](nb::sequence seq) {
            if (nb::len(seq) != 6) {
                throw nb::value_error("Input vector must be of shape (6,)");
            }
            return Screw3(
                Vec3(nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2])),
                Vec3(nb::cast<double>(seq[3]), nb::cast<double>(seq[4]), nb::cast<double>(seq[5]))
            );
        })
        .def("__repr__", [](const Screw3& s) {
            return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) + ", " +
                   std::to_string(s.ang.y) + ", " + std::to_string(s.ang.z) +
                   "), lin=Vec3(" + std::to_string(s.lin.x) + ", " +
                   std::to_string(s.lin.y) + ", " + std::to_string(s.lin.z) + "))";
        });
}

} // namespace termin
