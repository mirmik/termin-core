#include "common.hpp"

#include <string>

namespace termin {
namespace {

template <typename BoundsT, typename ScalarT>
void bind_bounds2_type(nb::module_& m, const char* name) {
    nb::class_<BoundsT>(m, name)
        .def(nb::init<>())
        .def(nb::init<ScalarT, ScalarT, ScalarT, ScalarT>(),
             nb::arg("x0"), nb::arg("y0"), nb::arg("x1"), nb::arg("y1"))
        .def_rw("x0", &BoundsT::x0)
        .def_rw("y0", &BoundsT::y0)
        .def_rw("x1", &BoundsT::x1)
        .def_rw("y1", &BoundsT::y1)
        .def("width", &BoundsT::width)
        .def("height", &BoundsT::height)
        .def("__getitem__", [](const BoundsT& b, int i) {
            switch (i) {
                case 0: return b.x0;
                case 1: return b.y0;
                case 2: return b.x1;
                case 3: return b.y1;
                default: throw nb::index_error("Bounds2 index out of range");
            }
        })
        .def("__setitem__", [](BoundsT& b, int i, ScalarT val) {
            switch (i) {
                case 0: b.x0 = val; return;
                case 1: b.y0 = val; return;
                case 2: b.x1 = val; return;
                case 3: b.y1 = val; return;
                default: throw nb::index_error("Bounds2 index out of range");
            }
        })
        .def("__len__", [](const BoundsT&) { return 4; })
        .def("__iter__", [](const BoundsT& b) {
            return nb::iter(nb::make_tuple(b.x0, b.y0, b.x1, b.y1));
        })
        .def("tolist", [](const BoundsT& b) {
            nb::list lst;
            lst.append(b.x0);
            lst.append(b.y0);
            lst.append(b.x1);
            lst.append(b.y1);
            return lst;
        })
        .def("copy", [](const BoundsT& b) { return b; })
        .def("__eq__", [](const BoundsT& a, const BoundsT& b) {
            return a.x0 == b.x0 && a.y0 == b.y0 && a.x1 == b.x1 && a.y1 == b.y1;
        })
        .def("__ne__", [](const BoundsT& a, const BoundsT& b) {
            return a.x0 != b.x0 || a.y0 != b.y0 || a.x1 != b.x1 || a.y1 != b.y1;
        })
        .def("__repr__", [name](const BoundsT& b) {
            return std::string(name) + "(" + std::to_string(b.x0) + ", " +
                   std::to_string(b.y0) + ", " + std::to_string(b.x1) + ", " +
                   std::to_string(b.y1) + ")";
        });
}

} // namespace

void bind_bounds2(nb::module_& m) {
    bind_bounds2_type<Bounds2f, float>(m, "Bounds2f");
}

} // namespace termin
