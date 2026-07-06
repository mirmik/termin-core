#include "common.hpp"

#include <string>

namespace termin {

namespace {

template <typename VecT, typename ScalarT>
void bind_vec2_type(nb::module_& m, const char* name) {
    nb::class_<VecT>(m, name)
        .def(nb::init<>())
        .def(nb::init<ScalarT, ScalarT>())
        .def_rw("x", &VecT::x)
        .def_rw("y", &VecT::y)
        .def("__getitem__", [](const VecT& v, int i) { return v[i]; })
        .def("__setitem__", [](VecT& v, int i, ScalarT val) { v[i] = val; })
        .def("__len__", [](const VecT&) { return 2; })
        .def("__iter__", [](const VecT& v) {
            return nb::iter(nb::make_tuple(v.x, v.y));
        })
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * ScalarT())
        .def(ScalarT() * nb::self)
        .def(nb::self / ScalarT())
        .def(-nb::self)
        .def("dot", &VecT::dot)
        .def("cross", &VecT::cross)
        .def("norm", &VecT::norm)
        .def("norm_squared", &VecT::norm_squared)
        .def("normalized", &VecT::normalized)
        .def_static("zero", &VecT::zero)
        .def_static("unit_x", &VecT::unit_x)
        .def_static("unit_y", &VecT::unit_y)
        .def("tolist", [](const VecT& v) {
            nb::list lst;
            lst.append(v.x);
            lst.append(v.y);
            return lst;
        })
        .def("copy", [](const VecT& v) { return v; })
        .def("__eq__", &VecT::operator==)
        .def("__ne__", &VecT::operator!=)
        .def("__repr__", [name](const VecT& v) {
            return std::string(name) + "(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ")";
        });
}

template <typename VecT>
void bind_vec2i_type(nb::module_& m, const char* name) {
    nb::class_<VecT>(m, name)
        .def(nb::init<>())
        .def(nb::init<int, int>())
        .def_rw("x", &VecT::x)
        .def_rw("y", &VecT::y)
        .def("__getitem__", [](const VecT& v, int i) { return v[i]; })
        .def("__setitem__", [](VecT& v, int i, int val) { v[i] = val; })
        .def("__len__", [](const VecT&) { return 2; })
        .def("__iter__", [](const VecT& v) {
            return nb::iter(nb::make_tuple(v.x, v.y));
        })
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * int())
        .def(int() * nb::self)
        .def(nb::self / int())
        .def(-nb::self)
        .def("dot", &VecT::dot)
        .def("cross", &VecT::cross)
        .def_static("zero", &VecT::zero)
        .def_static("unit_x", &VecT::unit_x)
        .def_static("unit_y", &VecT::unit_y)
        .def("to_double", &VecT::to_double)
        .def("to_float", &VecT::to_float)
        .def("tolist", [](const VecT& v) {
            nb::list lst;
            lst.append(v.x);
            lst.append(v.y);
            return lst;
        })
        .def("copy", [](const VecT& v) { return v; })
        .def("__eq__", &VecT::operator==)
        .def("__ne__", &VecT::operator!=)
        .def("__repr__", [name](const VecT& v) {
            return std::string(name) + "(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ")";
        });
}

} // namespace

void bind_vec2(nb::module_& m) {
    bind_vec2_type<Vec2, double>(m, "Vec2");
    bind_vec2_type<Vec2f, float>(m, "Vec2f");
    bind_vec2i_type<Vec2i>(m, "Vec2i");
}

} // namespace termin
