// tc_screw3.h - Spatial screw/twist/wrench operations
#ifndef TC_SCREW3_H
#define TC_SCREW3_H

#include "geom/tc_pose.h"
#include "geom/tc_vec3.h"
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_SCREW3(ang_, lin_)                                                  \
    tc_screw3                                                                  \
    {                                                                          \
        ang_, lin_                                                             \
    }
#else
#define TC_SCREW3(ang_, lin_)                                                  \
    (tc_screw3)                                                                \
    {                                                                          \
        ang_, lin_                                                             \
    }
#endif

#ifdef __cplusplus
extern "C"
{
#endif

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_new(tc_vec3 ang, tc_vec3 lin)
    {
        return TC_SCREW3(ang, lin);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_zero(void)
    {
        return TC_SCREW3(tc_vec3_zero(), tc_vec3_zero());
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_add(tc_screw3 a, tc_screw3 b)
    {
        return TC_SCREW3(tc_vec3_add(a.ang, b.ang), tc_vec3_add(a.lin, b.lin));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_sub(tc_screw3 a, tc_screw3 b)
    {
        return TC_SCREW3(tc_vec3_sub(a.ang, b.ang), tc_vec3_sub(a.lin, b.lin));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_scale(tc_screw3 s, double k)
    {
        return TC_SCREW3(tc_vec3_scale(s.ang, k), tc_vec3_scale(s.lin, k));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_div(tc_screw3 s, double k)
    {
        return tc_screw3_scale(s, 1.0 / k);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_neg(tc_screw3 s)
    {
        return TC_SCREW3(tc_vec3_neg(s.ang), tc_vec3_neg(s.lin));
    }

    TC_C_STATIC_INLINE double tc_screw3_dot(tc_screw3 a, tc_screw3 b)
    {
        return tc_vec3_dot(a.ang, b.ang) + tc_vec3_dot(a.lin, b.lin);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_cross_motion(tc_screw3 a,
                                                        tc_screw3 b)
    {
        return TC_SCREW3(tc_vec3_cross(a.ang, b.ang),
                         tc_vec3_add(tc_vec3_cross(a.ang, b.lin),
                                     tc_vec3_cross(a.lin, b.ang)));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_cross_force(tc_screw3 a, tc_screw3 b)
    {
        return TC_SCREW3(tc_vec3_add(tc_vec3_cross(a.ang, b.ang),
                                     tc_vec3_cross(a.lin, b.lin)),
                         tc_vec3_cross(a.ang, b.lin));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_rotated_by(tc_screw3 s,
                                                      tc_quat orientation)
    {
        return TC_SCREW3(tc_quat_rotate(orientation, s.ang),
                         tc_quat_rotate(orientation, s.lin));
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_inverse_rotated_by(tc_screw3 s, tc_quat orientation)
    {
        return tc_screw3_rotated_by(s, tc_quat_inverse(orientation));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_adjoint_pose(tc_screw3 s,
                                                        tc_pose3 pose)
    {
        tc_vec3 ang_world = tc_pose3_transform_vector(pose, s.ang);
        tc_vec3 lin_world = tc_vec3_add(tc_pose3_transform_vector(pose, s.lin),
                                        tc_vec3_cross(pose.lin, ang_world));
        return TC_SCREW3(ang_world, lin_world);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_adjoint_inv_pose(tc_screw3 s,
                                                            tc_pose3 pose)
    {
        return TC_SCREW3(
            tc_pose3_transform_vector(tc_pose3_inverse(pose), s.ang),
            tc_pose3_transform_vector(
                tc_pose3_inverse(pose),
                tc_vec3_sub(s.lin, tc_vec3_cross(pose.lin, s.ang))));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_coadjoint_pose(tc_screw3 s,
                                                          tc_pose3 pose)
    {
        tc_vec3 lin_world = tc_pose3_transform_vector(pose, s.lin);
        tc_vec3 ang_world = tc_vec3_add(tc_pose3_transform_vector(pose, s.ang),
                                        tc_vec3_cross(pose.lin, lin_world));
        return TC_SCREW3(ang_world, lin_world);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_coadjoint_inv_pose(tc_screw3 s,
                                                              tc_pose3 pose)
    {
        tc_pose3 inv = tc_pose3_inverse(pose);
        return TC_SCREW3(
            tc_pose3_transform_vector(
                inv, tc_vec3_sub(s.ang, tc_vec3_cross(pose.lin, s.lin))),
            tc_pose3_transform_vector(inv, s.lin));
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_velocity_at_offset(tc_screw3 s, tc_vec3 offset_from_origin)
    {
        return TC_SCREW3(
            s.ang,
            tc_vec3_add(s.lin, tc_vec3_cross(s.ang, offset_from_origin)));
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_velocity_at_origin_from_offset(
        tc_screw3 s, tc_vec3 offset_from_origin)
    {
        return TC_SCREW3(
            s.ang,
            tc_vec3_sub(s.lin, tc_vec3_cross(s.ang, offset_from_origin)));
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_wrench_at_offset(tc_screw3 s, tc_vec3 offset_from_origin)
    {
        return TC_SCREW3(
            tc_vec3_sub(s.ang, tc_vec3_cross(offset_from_origin, s.lin)),
            s.lin);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_wrench_at_origin_from_offset(
        tc_screw3 s, tc_vec3 offset_from_origin)
    {
        return TC_SCREW3(
            tc_vec3_add(s.ang, tc_vec3_cross(offset_from_origin, s.lin)),
            s.lin);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_transform_as_twist_by(tc_screw3 s,
                                                                 tc_pose3 pose)
    {
        return tc_screw3_adjoint_pose(s, pose);
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_inverse_transform_as_twist_by(tc_screw3 s, tc_pose3 pose)
    {
        return tc_screw3_adjoint_inv_pose(s, pose);
    }

    TC_C_STATIC_INLINE tc_screw3 tc_screw3_transform_as_wrench_by(tc_screw3 s,
                                                                  tc_pose3 pose)
    {
        return tc_screw3_coadjoint_pose(s, pose);
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_inverse_transform_as_wrench_by(tc_screw3 s, tc_pose3 pose)
    {
        return tc_screw3_coadjoint_inv_pose(s, pose);
    }

    TC_C_STATIC_INLINE void tc_screw3_to_vector_vw_order(tc_screw3 s,
                                                         double out[6])
    {
        out[0] = s.lin.x;
        out[1] = s.lin.y;
        out[2] = s.lin.z;
        out[3] = s.ang.x;
        out[4] = s.ang.y;
        out[5] = s.ang.z;
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_from_vector_vw_order(const double data[6])
    {
        return TC_SCREW3(TC_VEC3(data[3], data[4], data[5]),
                         TC_VEC3(data[0], data[1], data[2]));
    }

    TC_C_STATIC_INLINE void tc_screw3_to_vector_wv_order(tc_screw3 s,
                                                         double out[6])
    {
        out[0] = s.ang.x;
        out[1] = s.ang.y;
        out[2] = s.ang.z;
        out[3] = s.lin.x;
        out[4] = s.lin.y;
        out[5] = s.lin.z;
    }

    TC_C_STATIC_INLINE tc_screw3
    tc_screw3_from_vector_wv_order(const double data[6])
    {
        return TC_SCREW3(TC_VEC3(data[0], data[1], data[2]),
                         TC_VEC3(data[3], data[4], data[5]));
    }

    TC_C_STATIC_INLINE tc_pose3 tc_screw3_to_pose(tc_screw3 s)
    {
        double theta = tc_vec3_length(s.ang);
        if (theta < 1e-8)
        {
            return tc_pose3_new(tc_quat_identity(), s.lin);
        }
        tc_vec3 axis = tc_vec3_scale(s.ang, 1.0 / theta);
        return tc_pose3_new(tc_quat_from_axis_angle(axis, theta), s.lin);
    }

#ifdef __cplusplus
}
#endif

#endif // TC_SCREW3_H
