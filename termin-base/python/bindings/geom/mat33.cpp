#include "common.hpp"
#include <nanobind/stl/pair.h>

namespace termin {

void bind_mat33(nb::module_& m) {
    nb::class_<Mat33>(m, "Mat33")
        .def(nb::init<>())
        .def("__call__", [](const Mat33& m, int col, int row) { return m(col, row); })
        .def("__getitem__", [](const Mat33& m, std::pair<int, int> idx) {
            return m(idx.first, idx.second);
        })
        .def("__setitem__", [](Mat33& m, std::pair<int, int> idx, double val) {
            m(idx.first, idx.second) = val;
        })
        .def(nb::self * nb::self)
        .def("__matmul__", [](const Mat33& a, const Mat33& b) { return a * b; })
        .def("__matmul__", [](const Mat33& m, const Vec3& v) { return m.transform(v); })
        .def("transform", &Mat33::transform)
        .def("transposed", &Mat33::transposed)
        .def("determinant", &Mat33::determinant)
        .def("inverse", &Mat33::inverse)
        .def_static("identity", &Mat33::identity)
        .def_static("zero", &Mat33::zero)
        .def_static("scale", nb::overload_cast<double>(&Mat33::scale))
        .def_static("scale", nb::overload_cast<const Vec3&>(&Mat33::scale))
        .def_static("rotation_x", &Mat33::rotation_x)
        .def_static("rotation_y", &Mat33::rotation_y)
        .def_static("rotation_z", &Mat33::rotation_z)
        .def_static("rotation_axis_angle", &Mat33::rotation_axis_angle)
        .def("to_rows", [](const Mat33& mat) {
            double data[9];
            for (int row = 0; row < 3; ++row)
                for (int col = 0; col < 3; ++col)
                    data[row * 3 + col] = mat(col, row);
            return mat33_row_tuple(data);
        })
        .def("tolist", [](const Mat33& mat) {
            double data[9];
            for (int row = 0; row < 3; ++row)
                for (int col = 0; col < 3; ++col)
                    data[row * 3 + col] = mat(col, row);
            return mat33_row_tuple(data);
        })
        .def("__repr__", [](const Mat33&) {
            return "<Mat33>";
        })
        .def("to_float", &Mat33::to_float);

    nb::class_<Mat33f>(m, "Mat33f")
        .def(nb::init<>())
        .def("__call__", [](const Mat33f& m, int col, int row) { return m(col, row); })
        .def("__getitem__", [](const Mat33f& m, std::pair<int, int> idx) {
            return m(idx.first, idx.second);
        })
        .def("__setitem__", [](Mat33f& m, std::pair<int, int> idx, float val) {
            m(idx.first, idx.second) = val;
        })
        .def(nb::self * nb::self)
        .def("__matmul__", [](const Mat33f& a, const Mat33f& b) { return a * b; })
        .def("__matmul__", [](const Mat33f& m, const Vec3f& v) { return m.transform(v); })
        .def("__matmul__", [](const Mat33f& m, const Vec3& v) { return m.transform(v); })
        .def("transform", nb::overload_cast<const Vec3f&>(&Mat33f::transform, nb::const_))
        .def("transform", nb::overload_cast<const Vec3&>(&Mat33f::transform, nb::const_))
        .def("transposed", &Mat33f::transposed)
        .def("determinant", &Mat33f::determinant)
        .def("inverse", &Mat33f::inverse)
        .def_static("identity", &Mat33f::identity)
        .def_static("zero", &Mat33f::zero)
        .def_static("scale", nb::overload_cast<float>(&Mat33f::scale))
        .def_static("scale", nb::overload_cast<const Vec3f&>(&Mat33f::scale))
        .def_static("rotation_x", &Mat33f::rotation_x)
        .def_static("rotation_y", &Mat33f::rotation_y)
        .def_static("rotation_z", &Mat33f::rotation_z)
        .def_static("rotation_axis_angle", &Mat33f::rotation_axis_angle)
        .def("to_rows", [](const Mat33f& mat) {
            double data[9];
            for (int row = 0; row < 3; ++row)
                for (int col = 0; col < 3; ++col)
                    data[row * 3 + col] = mat(col, row);
            return mat33_row_tuple(data);
        })
        .def("tolist", [](const Mat33f& mat) {
            double data[9];
            for (int row = 0; row < 3; ++row)
                for (int col = 0; col < 3; ++col)
                    data[row * 3 + col] = mat(col, row);
            return mat33_row_tuple(data);
        })
        .def("__repr__", [](const Mat33f&) {
            return "<Mat33f>";
        });
}

} // namespace termin
