#include "common.hpp"

#include <stdexcept>

namespace termin {

void bind_affine3(nb::module_& m) {
    nb::class_<Basis3d>(m, "Basis3d")
        .def(nb::init<>())
        .def("__init__", [](Basis3d* self, const Vec3& x, const Vec3& y, const Vec3& z) {
            new (self) Basis3d{x, y, z};
        }, nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def_rw("x", &Basis3d::x)
        .def_rw("y", &Basis3d::y)
        .def_rw("z", &Basis3d::z)
        .def("__matmul__", [](const Basis3d& a, const Basis3d& b) { return a * b; })
        .def("__matmul__", [](const Basis3d& basis, const Vec3& vector) {
            return basis.transform_vector(vector);
        })
        .def("transform_vector", &Basis3d::transform_vector)
        .def("determinant", &Basis3d::determinant)
        .def("is_finite", &Basis3d::is_finite)
        .def("try_inverse", [](const Basis3d& basis, double epsilon) -> nb::object {
            Basis3d inverse;
            if (!basis.try_inverse(inverse, epsilon)) {
                return nb::none();
            }
            return nb::cast(inverse);
        }, nb::arg("epsilon") = 1.0e-12)
        .def("inverse", [](const Basis3d& basis, double epsilon) {
            Basis3d inverse;
            if (!basis.try_inverse(inverse, epsilon)) {
                throw std::runtime_error("Basis3d is singular and cannot be inverted");
            }
            return inverse;
        }, nb::arg("epsilon") = 1.0e-12)
        .def("to_rows", [](const Basis3d& basis) {
            const double data[9] = {
                basis.x.x, basis.y.x, basis.z.x,
                basis.x.y, basis.y.y, basis.z.y,
                basis.x.z, basis.y.z, basis.z.z,
            };
            return mat33_row_tuple(data);
        })
        .def_static("identity", &Basis3d::identity)
        .def_static("from_quat", &Basis3d::from_quat)
        .def_static(
            "scaling",
            nb::overload_cast<double, double, double>(&Basis3d::scaling),
            nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def_static(
            "scaling",
            nb::overload_cast<double>(&Basis3d::scaling),
            nb::arg("uniform"))
        .def("__repr__", [](const Basis3d&) { return "<Basis3d>"; });

    nb::class_<Affine3d>(m, "Affine3d")
        .def(nb::init<>())
        .def("__init__", [](Affine3d* self, const Basis3d& basis, const Vec3& translation) {
            new (self) Affine3d{basis, translation};
        }, nb::arg("basis"), nb::arg("translation"))
        .def_rw("basis", &Affine3d::basis)
        .def_rw("translation", &Affine3d::translation)
        .def("__matmul__", [](const Affine3d& a, const Affine3d& b) { return a * b; })
        .def("transform_point", &Affine3d::transform_point)
        .def("transform_vector", &Affine3d::transform_vector)
        .def("determinant", &Affine3d::determinant)
        .def("is_finite", &Affine3d::is_finite)
        .def("try_inverse", [](const Affine3d& affine, double epsilon) -> nb::object {
            Affine3d inverse;
            if (!affine.try_inverse(inverse, epsilon)) {
                return nb::none();
            }
            return nb::cast(inverse);
        }, nb::arg("epsilon") = 1.0e-12)
        .def("inverse", [](const Affine3d& affine, double epsilon) {
            Affine3d inverse;
            if (!affine.try_inverse(inverse, epsilon)) {
                throw std::runtime_error("Affine3d is singular and cannot be inverted");
            }
            return inverse;
        }, nb::arg("epsilon") = 1.0e-12)
        .def("as_matrix", [](const Affine3d& affine) {
            double column_major[16];
            double row_major[16];
            affine.matrix4(column_major);
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    row_major[row * 4 + col] = column_major[col * 4 + row];
                }
            }
            return mat44_row_tuple(row_major);
        })
        .def_static("identity", &Affine3d::identity)
        .def_static(
            "from_translation",
            nb::overload_cast<const Vec3&>(&Affine3d::from_translation))
        .def_static("rotation", &Affine3d::from_rotation)
        .def_static(
            "scaling",
            nb::overload_cast<double, double, double>(&Affine3d::scaling),
            nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def_static("scaling", nb::overload_cast<double>(&Affine3d::scaling))
        .def_static("trs", &Affine3d::trs)
        .def("__repr__", [](const Affine3d&) { return "<Affine3d>"; });
}

} // namespace termin
