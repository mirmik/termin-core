#include "common.hpp"

namespace termin {

namespace {

Vec2 object_to_vec2(nb::handle obj) {
    if (nb::isinstance<Vec2>(obj)) {
        return nb::cast<Vec2>(obj);
    }
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    if (nb::len(seq) != 2) {
        throw nb::value_error("Input vector must be of shape (2,)");
    }
    return Vec2{nb::cast<double>(seq[0]), nb::cast<double>(seq[1])};
}

double object_to_scalar(nb::handle obj) {
    if (nb::isinstance<nb::sequence>(obj)) {
        nb::sequence seq = nb::cast<nb::sequence>(obj);
        if (nb::len(seq) != 1) {
            throw nb::value_error("ang must be a scalar or a one-element sequence");
        }
        return nb::cast<double>(seq[0]);
    }
    return nb::cast<double>(obj);
}

void sequence_to_array3(nb::handle obj, double* out) {
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    if (nb::len(seq) != 3) {
        throw nb::value_error("Input vector must be of shape (3,)");
    }
    out[0] = nb::cast<double>(seq[0]);
    out[1] = nb::cast<double>(seq[1]);
    out[2] = nb::cast<double>(seq[2]);
}

} // namespace

void bind_screw2(nb::module_& m) {
    nb::class_<Screw2>(m, "Screw2")
        .def(nb::init<>())
        .def(nb::init<double, const Vec2&>(), nb::arg("ang"), nb::arg("lin"))
        .def("__init__", [](Screw2* self, nb::object ang, nb::object lin) {
            new (self) Screw2{object_to_scalar(ang), object_to_vec2(lin)};
        }, nb::arg("ang"), nb::arg("lin"))
        .def_rw("ang", &Screw2::ang)
        .def_prop_rw("lin",
            [](const Screw2& s) { return s.lin; },
            [](Screw2& s, nb::object lin) { s.lin = object_to_vec2(lin); })
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * double())
        .def(double() * nb::self)
        .def(nb::self / double())
        .def(-nb::self)
        .def("moment", &Screw2::moment)
        .def("vector", &Screw2::vector)
        .def("copy", &Screw2::copy)
        .def("kinematic_carry", [](const Screw2& self, nb::object arm) {
            return self.kinematic_carry(object_to_vec2(arm));
        })
        .def("force_carry", [](const Screw2& self, nb::object arm) {
            return self.force_carry(object_to_vec2(arm));
        })
        .def("twist_carry", [](const Screw2& self, nb::object arm) {
            return self.twist_carry(object_to_vec2(arm));
        })
        .def("wrench_carry", [](const Screw2& self, nb::object arm) {
            return self.wrench_carry(object_to_vec2(arm));
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
        .def_static("from_vector_vw_order", [](nb::object vec) {
            double data[3];
            sequence_to_array3(vec, data);
            return Screw2::from_vector_vw_order(data);
        })
        .def_static("from_vector_wv_order", [](nb::object vec) {
            double data[3];
            sequence_to_array3(vec, data);
            return Screw2::from_vector_wv_order(data);
        })
        .def("__repr__", [](const Screw2& s) {
            return "Screw2(ang=" + std::to_string(s.ang) + ", lin=Vec2(" +
                   std::to_string(s.lin.x) + ", " + std::to_string(s.lin.y) + "))";
        });
}

} // namespace termin
