#include "common.hpp"

namespace termin {

void bind_screw2(nb::module_& m) {
    nb::class_<Screw2>(m, "Screw2")
        .def(nb::init<>())
        .def(nb::init<double, const Vec2&>(), nb::arg("ang"), nb::arg("lin"))
        .def_rw("ang", &Screw2::ang)
        .def_prop_rw("lin",
            [](const Screw2& s) { return s.lin; },
            [](Screw2& s, const Vec2& lin) { s.lin = lin; })
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * double())
        .def(double() * nb::self)
        .def(nb::self / double())
        .def(-nb::self)
        .def("moment", &Screw2::moment)
        .def("vector", &Screw2::vector)
        .def("copy", &Screw2::copy)
        .def("kinematic_carry", [](const Screw2& self, const Vec2& arm) {
            return self.kinematic_carry(arm);
        })
        .def("force_carry", [](const Screw2& self, const Vec2& arm) {
            return self.force_carry(arm);
        })
        .def("twist_carry", [](const Screw2& self, const Vec2& arm) {
            return self.twist_carry(arm);
        })
        .def("wrench_carry", [](const Screw2& self, const Vec2& arm) {
            return self.wrench_carry(arm);
        })
        .def("transform_by", &Screw2::transform_by)
        .def("rotated_by", &Screw2::rotated_by)
        .def("inverse_transform_by", &Screw2::inverse_transform_by)
        .def("transform_as_twist_by", &Screw2::transform_as_twist_by)
        .def("inverse_transform_as_twist_by", &Screw2::inverse_transform_as_twist_by)
        .def("transform_as_wrench_by", &Screw2::transform_as_wrench_by)
        .def("inverse_transform_as_wrench_by", &Screw2::inverse_transform_as_wrench_by)
        .def("to_pose", &Screw2::to_pose)
        .def("to_vector_vw_order", [](const Screw2& s) {
            return nb::make_tuple(s.lin.x, s.lin.y, s.ang);
        })
        .def("to_vector_wv_order", [](const Screw2& s) {
            return nb::make_tuple(s.ang, s.lin.x, s.lin.y);
        })
        .def_static("zero", &Screw2::zero)
        .def_static("from_vector_vw_order", [](const Vec3& vec) {
            double data[3] = {vec.x, vec.y, vec.z};
            return Screw2::from_vector_vw_order(data);
        })
        .def_static("from_vector_wv_order", [](const Vec3& vec) {
            double data[3] = {vec.x, vec.y, vec.z};
            return Screw2::from_vector_wv_order(data);
        })
        .def("__repr__", [](const Screw2& s) {
            return "Screw2(ang=" + std::to_string(s.ang) + ", lin=Vec2(" +
                   std::to_string(s.lin.x) + ", " + std::to_string(s.lin.y) + "))";
        });
}

} // namespace termin
