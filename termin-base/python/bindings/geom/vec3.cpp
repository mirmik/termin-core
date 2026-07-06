#include "common.hpp"

namespace termin {

void bind_vec3(nb::module_& m) {
    nb::class_<Vec3>(m, "Vec3")
        .def(nb::init<>())
        .def(nb::init<double, double, double>())
        .def("__init__", [](Vec3* self, nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
            double* ptr = arr.data();
            new (self) Vec3{ptr[0], ptr[1], ptr[2]};
        })
        .def_rw("x", &Vec3::x)
        .def_rw("y", &Vec3::y)
        .def_rw("z", &Vec3::z)
        .def("__getitem__", [](const Vec3& v, int i) { return v[i]; })
        .def("__setitem__", [](Vec3& v, int i, double val) { v[i] = val; })
        .def("__len__", [](const Vec3&) { return 3; })
        .def("__iter__", [](const Vec3& v) {
            return nb::iter(nb::make_tuple(v.x, v.y, v.z));
        })
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * double())
        .def(double() * nb::self)
        .def(nb::self / double())
        .def(-nb::self)
        .def("dot", &Vec3::dot)
        .def("cross", &Vec3::cross)
        .def("norm", &Vec3::norm)
        .def("norm_squared", &Vec3::norm_squared)
        .def("normalized", &Vec3::normalized)
        .def_static("zero", &Vec3::zero)
        .def_static("unit_x", &Vec3::unit_x)
        .def_static("unit_y", &Vec3::unit_y)
        .def_static("unit_z", &Vec3::unit_z)
        .def_static("right", &Vec3::right)
        .def_static("left", &Vec3::left)
        .def_static("forward", &Vec3::forward)
        .def_static("backward", &Vec3::backward)
        .def_static("up", &Vec3::up)
        .def_static("down", &Vec3::down)
        .def_static("angle", &Vec3::angle,
            nb::arg("a"), nb::arg("b"),
            "Angle between two vectors in radians")
        .def_static("angle_degrees", &Vec3::angle_degrees,
            nb::arg("a"), nb::arg("b"),
            "Angle between two vectors in degrees")
        .def("to_numpy", &vec3_to_numpy)
        .def("tolist", [](const Vec3& v) {
            nb::list lst;
            lst.append(v.x);
            lst.append(v.y);
            lst.append(v.z);
            return lst;
        })
        .def("copy", [](const Vec3& v) { return v; })
        .def("__eq__", [](const Vec3& a, const Vec3& b) {
            return a.x == b.x && a.y == b.y && a.z == b.z;
        })
        .def("__ne__", [](const Vec3& a, const Vec3& b) {
            return a.x != b.x || a.y != b.y || a.z != b.z;
        })
        .def("approx_eq", [](const Vec3& a, const Vec3& b, double eps) {
            return std::abs(a.x - b.x) < eps &&
                   std::abs(a.y - b.y) < eps &&
                   std::abs(a.z - b.z) < eps;
        }, nb::arg("other"), nb::arg("eps") = 1e-9)
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });

    nb::class_<Vec3i>(m, "Vec3i")
        .def(nb::init<>())
        .def(nb::init<int, int, int>())
        .def_rw("x", &Vec3i::x)
        .def_rw("y", &Vec3i::y)
        .def_rw("z", &Vec3i::z)
        .def("__getitem__", [](const Vec3i& v, int i) { return v[i]; })
        .def("__setitem__", [](Vec3i& v, int i, int val) { v[i] = val; })
        .def("__len__", [](const Vec3i&) { return 3; })
        .def("__iter__", [](const Vec3i& v) {
            return nb::iter(nb::make_tuple(v.x, v.y, v.z));
        })
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * int())
        .def(int() * nb::self)
        .def(nb::self / int())
        .def(-nb::self)
        .def("dot", &Vec3i::dot)
        .def("cross", &Vec3i::cross)
        .def("to_double", &Vec3i::to_double)
        .def_static("zero", &Vec3i::zero)
        .def_static("unit_x", &Vec3i::unit_x)
        .def_static("unit_y", &Vec3i::unit_y)
        .def_static("unit_z", &Vec3i::unit_z)
        .def_static("right", &Vec3i::right)
        .def_static("left", &Vec3i::left)
        .def_static("forward", &Vec3i::forward)
        .def_static("backward", &Vec3i::backward)
        .def_static("up", &Vec3i::up)
        .def_static("down", &Vec3i::down)
        .def("tolist", [](const Vec3i& v) {
            nb::list lst;
            lst.append(v.x);
            lst.append(v.y);
            lst.append(v.z);
            return lst;
        })
        .def("copy", [](const Vec3i& v) { return v; })
        .def("__eq__", &Vec3i::operator==)
        .def("__ne__", &Vec3i::operator!=)
        .def("__repr__", [](const Vec3i& v) {
            return "Vec3i(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });
}

} // namespace termin
