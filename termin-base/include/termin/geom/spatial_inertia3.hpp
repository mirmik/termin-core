#pragma once

#include "mat33.hpp"
#include "mat66.hpp"
#include "pose3.hpp"
#include "screw3.hpp"

#include <cmath>

namespace termin
{
    // Spatial inertia expressed at a reference-frame origin. The translation
    // of inertia_frame is the center of mass and its rotation maps principal
    // inertia axes into the reference frame.
    struct SpatialInertia3
    {
        double mass = 1.0;
        Vec3 principal_moments{1.0, 1.0, 1.0};
        Pose3 inertia_frame = Pose3::identity();

        [[nodiscard]] bool is_finite() const noexcept
        {
            return std::isfinite(mass) && std::isfinite(principal_moments.x) &&
                   std::isfinite(principal_moments.y) &&
                   std::isfinite(principal_moments.z) &&
                   std::isfinite(inertia_frame.lin.x) &&
                   std::isfinite(inertia_frame.lin.y) &&
                   std::isfinite(inertia_frame.lin.z) &&
                   std::isfinite(inertia_frame.ang.x) &&
                   std::isfinite(inertia_frame.ang.y) &&
                   std::isfinite(inertia_frame.ang.z) &&
                   std::isfinite(inertia_frame.ang.w);
        }

        [[nodiscard]] bool is_valid() const noexcept
        {
            return is_finite() && mass > 0.0 && principal_moments.x > 0.0 &&
                   principal_moments.y > 0.0 && principal_moments.z > 0.0 &&
                   inertia_frame.ang.norm() > 1e-10;
        }

        [[nodiscard]] Mat33 central_inertia() const noexcept
        {
            const Mat33 rotation = Mat33::rotation(inertia_frame.ang);
            return rotation * Mat33::scale(principal_moments) *
                   rotation.transposed();
        }

        // Matrix for the explicit dense order [linear, angular].
        [[nodiscard]] Mat66 matrix_vw() const noexcept
        {
            const Vec3 center = inertia_frame.lin;
            const Mat33 center_cross = Mat33::cross_product(center);
            const Mat33 central = central_inertia();
            Mat66 result;

            for (int axis = 0; axis < 3; ++axis)
            {
                result(axis, axis) = mass;
            }

            for (int row = 0; row < 3; ++row)
            {
                for (int column = 0; column < 3; ++column)
                {
                    result(column + 3, row) = -mass * center_cross(column, row);
                    result(column, row + 3) = mass * center_cross(column, row);
                    result(column + 3, row + 3) =
                        central(column, row) +
                        mass * ((row == column ? center.dot(center) : 0.0) -
                                center[row] * center[column]);
                }
            }
            return result;
        }

        [[nodiscard]] Screw3 momentum(Screw3 velocity) const noexcept
        {
            const Vec3 center = inertia_frame.lin;
            const Vec3 linear_momentum =
                (velocity.lin + velocity.ang.cross(center)) * mass;
            const Vec3 angular_momentum =
                central_inertia().transform(velocity.ang) +
                center.cross(linear_momentum);
            return {angular_momentum, linear_momentum};
        }

        [[nodiscard]] double kinetic_energy(Screw3 velocity) const noexcept
        {
            return 0.5 * velocity.dot(momentum(velocity));
        }

        [[nodiscard]] SpatialInertia3
        rotated_by(Quat orientation) const noexcept
        {
            return transformed_by({orientation.normalized(), Vec3::zero()});
        }

        // Transform the represented mass distribution with pose. The returned
        // inertia is expressed at the destination-frame origin.
        [[nodiscard]] SpatialInertia3
        transformed_by(const Pose3& pose) const noexcept
        {
            return {
                mass,
                principal_moments,
                (pose.normalized() * inertia_frame).normalized(),
            };
        }

        [[nodiscard]] SpatialInertia3
        inverse_transformed_by(const Pose3& pose) const noexcept
        {
            return transformed_by(pose.inverse());
        }
    };
} // namespace termin
