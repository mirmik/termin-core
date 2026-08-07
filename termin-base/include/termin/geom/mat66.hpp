#pragma once

#include "vec6.hpp"

#include <cstring>

namespace termin {
    // Fixed-size 6x6 double matrix in the same column-major convention as
    // Mat33 and Mat44. Element access is matrix(column, row).
    struct Mat66 {
        double data[36];

        Mat66() {
            std::memset(data, 0, sizeof(data));
        }

        double& operator()(int column, int row) {
            return data[column * 6 + row];
        }

        double operator()(int column, int row) const {
            return data[column * 6 + row];
        }

        double* ptr() {
            return data;
        }

        const double* ptr() const {
            return data;
        }

        static Mat66 identity() {
            Mat66 result;
            for (int axis = 0; axis < 6; ++axis) {
                result(axis, axis) = 1.0;
            }
            return result;
        }

        static Mat66 zero() {
            return Mat66{};
        }

        Mat66 operator*(const Mat66& other) const {
            Mat66 result;
            for (int column = 0; column < 6; ++column) {
                for (int row = 0; row < 6; ++row) {
                    for (int inner = 0; inner < 6; ++inner) {
                        result(column, row) += (*this)(inner, row) * other(column, inner);
                    }
                }
            }
            return result;
        }

        Vec6 transform(const Vec6& vector) const {
            Vec6 result;
            for (int row = 0; row < 6; ++row) {
                for (int column = 0; column < 6; ++column) {
                    result[row] += (*this)(column, row) * vector[column];
                }
            }
            return result;
        }

        Mat66 transposed() const {
            Mat66 result;
            for (int column = 0; column < 6; ++column) {
                for (int row = 0; row < 6; ++row) {
                    result(column, row) = (*this)(row, column);
                }
            }
            return result;
        }
    };
} // namespace termin
