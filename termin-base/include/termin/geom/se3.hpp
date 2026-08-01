#pragma once

#include "pose3.hpp"
#include "screw3.hpp"

#include <cmath>

namespace termin
{
    namespace se3_detail
    {
        inline Quat so3_exp(Vec3 rotation_vector) noexcept
        {
            const double angle = rotation_vector.norm();
            if (angle < 1e-12)
            {
                return Quat{
                    0.5 * rotation_vector.x,
                    0.5 * rotation_vector.y,
                    0.5 * rotation_vector.z,
                    1.0,
                }
                    .normalized();
            }
            return Quat::from_axis_angle(rotation_vector / angle, angle);
        }

        inline Vec3 so3_log(Quat orientation) noexcept
        {
            orientation = orientation.normalized();
            if (orientation.w < 0.0)
            {
                orientation = {
                    -orientation.x,
                    -orientation.y,
                    -orientation.z,
                    -orientation.w,
                };
            }

            const Vec3 imaginary{orientation.x, orientation.y, orientation.z};
            const double sine_half = imaginary.norm();
            if (sine_half < 1e-12)
            {
                return imaginary * 2.0;
            }

            const double angle = 2.0 * std::atan2(sine_half, orientation.w);
            return imaginary * (angle / sine_half);
        }

        inline Vec3 left_jacobian_apply(Vec3 rotation_vector,
                                        Vec3 value) noexcept
        {
            const double angle_squared = rotation_vector.dot(rotation_vector);
            double first_coefficient;
            double second_coefficient;
            if (angle_squared < 1e-10)
            {
                first_coefficient = 0.5 - angle_squared / 24.0;
                second_coefficient = 1.0 / 6.0 - angle_squared / 120.0;
            }
            else
            {
                const double angle = std::sqrt(angle_squared);
                first_coefficient = (1.0 - std::cos(angle)) / angle_squared;
                second_coefficient =
                    (angle - std::sin(angle)) / (angle_squared * angle);
            }

            const Vec3 first_cross = rotation_vector.cross(value);
            return value + first_cross * first_coefficient +
                   rotation_vector.cross(first_cross) * second_coefficient;
        }

        inline Vec3 left_jacobian_inverse_apply(Vec3 rotation_vector,
                                                Vec3 value) noexcept
        {
            const double angle_squared = rotation_vector.dot(rotation_vector);
            double coefficient;
            if (angle_squared < 1e-10)
            {
                coefficient = 1.0 / 12.0 + angle_squared / 720.0;
            }
            else
            {
                const double angle = std::sqrt(angle_squared);
                coefficient =
                    (1.0 - 0.5 * angle / std::tan(0.5 * angle)) / angle_squared;
            }

            const Vec3 first_cross = rotation_vector.cross(value);
            return value - first_cross * 0.5 +
                   rotation_vector.cross(first_cross) * coefficient;
        }
    } // namespace se3_detail

    // Exponential map from a tangent in se(3) to a rigid transform in SE(3).
    // Screw3::lin is coupled to Screw3::ang through the SO(3) left Jacobian.
    [[nodiscard]] inline Pose3 se3_exp(Screw3 tangent) noexcept
    {
        return {
            se3_detail::so3_exp(tangent.ang),
            se3_detail::left_jacobian_apply(tangent.ang, tangent.lin),
        };
    }

    // Principal logarithm of a rigid transform. The angular result has norm
    // at most pi; exp(log(pose)) recovers the represented transform.
    [[nodiscard]] inline Screw3 se3_log(const Pose3& pose) noexcept
    {
        const Vec3 angular = se3_detail::so3_log(pose.ang);
        return {
            angular,
            se3_detail::left_jacobian_inverse_apply(angular, pose.lin),
        };
    }
} // namespace termin
