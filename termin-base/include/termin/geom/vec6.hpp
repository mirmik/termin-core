#pragma once

#include <cmath>
#include <cstddef>

namespace termin {
    struct Vec6 {
        double data[6]{};

        Vec6() = default;

        Vec6(double value_0, double value_1, double value_2, double value_3, double value_4, double value_5)
            : data{value_0, value_1, value_2, value_3, value_4, value_5} {}

        double& operator[](int index) {
            return data[index];
        }

        double operator[](int index) const {
            return data[index];
        }

        double* ptr() {
            return data;
        }

        const double* ptr() const {
            return data;
        }

        static constexpr std::size_t size() {
            return 6;
        }

        Vec6 operator+(const Vec6& other) const {
            Vec6 result;
            for (int index = 0; index < 6; ++index) {
                result[index] = (*this)[index] + other[index];
            }
            return result;
        }

        Vec6 operator-(const Vec6& other) const {
            Vec6 result;
            for (int index = 0; index < 6; ++index) {
                result[index] = (*this)[index] - other[index];
            }
            return result;
        }

        Vec6 operator*(double scalar) const {
            Vec6 result;
            for (int index = 0; index < 6; ++index) {
                result[index] = (*this)[index] * scalar;
            }
            return result;
        }

        Vec6 operator/(double scalar) const {
            return *this * (1.0 / scalar);
        }

        Vec6 operator-() const {
            return *this * -1.0;
        }

        Vec6& operator+=(const Vec6& other) {
            for (int index = 0; index < 6; ++index) {
                (*this)[index] += other[index];
            }
            return *this;
        }

        Vec6& operator-=(const Vec6& other) {
            for (int index = 0; index < 6; ++index) {
                (*this)[index] -= other[index];
            }
            return *this;
        }

        Vec6& operator*=(double scalar) {
            for (double& value : data) {
                value *= scalar;
            }
            return *this;
        }

        Vec6& operator/=(double scalar) {
            return *this *= 1.0 / scalar;
        }

        bool operator==(const Vec6& other) const {
            for (int index = 0; index < 6; ++index) {
                if ((*this)[index] != other[index]) {
                    return false;
                }
            }
            return true;
        }

        bool operator!=(const Vec6& other) const {
            return !(*this == other);
        }

        double dot(const Vec6& other) const {
            double result = 0.0;
            for (int index = 0; index < 6; ++index) {
                result += (*this)[index] * other[index];
            }
            return result;
        }

        double norm_squared() const {
            return dot(*this);
        }

        double norm() const {
            return std::sqrt(norm_squared());
        }

        Vec6 normalized() const {
            const double magnitude = norm();
            return magnitude > 1e-10 ? *this / magnitude : Vec6::zero();
        }

        static Vec6 zero() {
            return {};
        }
    };

    inline Vec6 operator*(double scalar, const Vec6& vector) {
        return vector * scalar;
    }
} // namespace termin
