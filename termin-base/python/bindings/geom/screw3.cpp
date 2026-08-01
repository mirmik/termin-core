#include "common.hpp"

namespace termin
{

    void bind_screw3(nb::module_& m)
    {
        nb::class_<Screw3>(m, "Screw3")
            .def(nb::init<>())
            .def(nb::init<const Vec3&, const Vec3&>(),
                 nb::arg("ang"),
                 nb::arg("lin"))
            .def_rw("ang", &Screw3::ang)
            .def_rw("lin", &Screw3::lin)
            .def(nb::self + nb::self)
            .def(nb::self - nb::self)
            .def(nb::self * double())
            .def(nb::self / double())
            .def(double() * nb::self)
            .def(-nb::self)
            .def("dot", &Screw3::dot)
            .def("cross_motion", &Screw3::cross_motion)
            .def("cross_force", &Screw3::cross_force)
            .def("rotated_by", &Screw3::rotated_by)
            .def("inverse_rotated_by", &Screw3::inverse_rotated_by)
            .def("transform_as_twist_by", &Screw3::transform_as_twist_by)
            .def("inverse_transform_as_twist_by",
                 &Screw3::inverse_transform_as_twist_by)
            .def("transform_as_wrench_by", &Screw3::transform_as_wrench_by)
            .def("inverse_transform_as_wrench_by",
                 &Screw3::inverse_transform_as_wrench_by)
            .def("velocity_at_offset", &Screw3::velocity_at_offset)
            .def("velocity_at_origin_from_offset",
                 &Screw3::velocity_at_origin_from_offset)
            .def("wrench_at_offset", &Screw3::wrench_at_offset)
            .def("wrench_at_origin_from_offset",
                 &Screw3::wrench_at_origin_from_offset)
            .def("scaled", &Screw3::scaled)
            .def("copy", [](const Screw3& s) { return s; })
            .def("to_vector_vw_order",
                 [](const Screw3& s)
                 {
                     return nb::make_tuple(
                         s.lin.x, s.lin.y, s.lin.z, s.ang.x, s.ang.y, s.ang.z);
                 })
            .def("to_vector_wv_order",
                 [](const Screw3& s)
                 {
                     return nb::make_tuple(
                         s.ang.x, s.ang.y, s.ang.z, s.lin.x, s.lin.y, s.lin.z);
                 })
            .def("to_vw_array",
                 [](const Screw3& s)
                 {
                     return nb::make_tuple(
                         s.lin.x, s.lin.y, s.lin.z, s.ang.x, s.ang.y, s.ang.z);
                 })
            .def("to_wv_array",
                 [](const Screw3& s)
                 {
                     return nb::make_tuple(
                         s.ang.x, s.ang.y, s.ang.z, s.lin.x, s.lin.y, s.lin.z);
                 })
            .def("adjoint", &Screw3::adjoint)
            .def("adjoint_inv", &Screw3::adjoint_inv)
            .def("coadjoint", &Screw3::coadjoint)
            .def("coadjoint_inv", &Screw3::coadjoint_inv)
            .def_static("zero", &Screw3::zero)
            .def_static("from_vector_vw_order",
                        [](nb::sequence seq)
                        {
                            if (nb::len(seq) != 6)
                            {
                                throw nb::value_error(
                                    "Input vector must be of shape (6,)");
                            }
                            return Screw3(Vec3(nb::cast<double>(seq[3]),
                                               nb::cast<double>(seq[4]),
                                               nb::cast<double>(seq[5])),
                                          Vec3(nb::cast<double>(seq[0]),
                                               nb::cast<double>(seq[1]),
                                               nb::cast<double>(seq[2])));
                        })
            .def_static("from_vector_wv_order",
                        [](nb::sequence seq)
                        {
                            if (nb::len(seq) != 6)
                            {
                                throw nb::value_error(
                                    "Input vector must be of shape (6,)");
                            }
                            return Screw3(Vec3(nb::cast<double>(seq[0]),
                                               nb::cast<double>(seq[1]),
                                               nb::cast<double>(seq[2])),
                                          Vec3(nb::cast<double>(seq[3]),
                                               nb::cast<double>(seq[4]),
                                               nb::cast<double>(seq[5])));
                        })
            .def_static("from_vw_array",
                        [](nb::sequence seq)
                        {
                            if (nb::len(seq) != 6)
                            {
                                throw nb::value_error(
                                    "Input vector must be of shape (6,)");
                            }
                            return Screw3(Vec3(nb::cast<double>(seq[3]),
                                               nb::cast<double>(seq[4]),
                                               nb::cast<double>(seq[5])),
                                          Vec3(nb::cast<double>(seq[0]),
                                               nb::cast<double>(seq[1]),
                                               nb::cast<double>(seq[2])));
                        })
            .def_static("from_wv_array",
                        [](nb::sequence seq)
                        {
                            if (nb::len(seq) != 6)
                            {
                                throw nb::value_error(
                                    "Input vector must be of shape (6,)");
                            }
                            return Screw3(Vec3(nb::cast<double>(seq[0]),
                                               nb::cast<double>(seq[1]),
                                               nb::cast<double>(seq[2])),
                                          Vec3(nb::cast<double>(seq[3]),
                                               nb::cast<double>(seq[4]),
                                               nb::cast<double>(seq[5])));
                        })
            .def("__repr__",
                 [](const Screw3& s)
                 {
                     return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) +
                            ", " + std::to_string(s.ang.y) + ", " +
                            std::to_string(s.ang.z) + "), lin=Vec3(" +
                            std::to_string(s.lin.x) + ", " +
                            std::to_string(s.lin.y) + ", " +
                            std::to_string(s.lin.z) + "))";
                 });

        m.def("se3_exp", &se3_exp, nb::arg("tangent"));
        m.def("se3_log", &se3_log, nb::arg("pose"));
    }

} // namespace termin
