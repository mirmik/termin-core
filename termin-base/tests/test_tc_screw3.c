#include <geom/tc_screw3.h>

#include "guard_c.h"

int main(void) {
    const tc_screw3 screw = tc_screw3_new(TC_VEC3(2.0, 4.0, 6.0), TC_VEC3(8.0, 10.0, 12.0));
    const tc_screw3 half = tc_screw3_div(screw, 2.0);
    GUARD_C_CHECK(half.ang.x == 1.0);
    GUARD_C_CHECK(half.ang.y == 2.0);
    GUARD_C_CHECK(half.ang.z == 3.0);
    GUARD_C_CHECK(half.lin.x == 4.0);
    GUARD_C_CHECK(half.lin.y == 5.0);
    GUARD_C_CHECK(half.lin.z == 6.0);

    double vw[6];
    tc_screw3_to_vector_vw_order(screw, vw);
    GUARD_C_CHECK(vw[0] == 8.0);
    GUARD_C_CHECK(vw[3] == 2.0);
    const tc_screw3 recovered_vw = tc_screw3_from_vector_vw_order(vw);
    GUARD_C_CHECK(recovered_vw.ang.z == screw.ang.z);
    GUARD_C_CHECK(recovered_vw.lin.z == screw.lin.z);

    double wv[6];
    tc_screw3_to_vector_wv_order(screw, wv);
    GUARD_C_CHECK(wv[0] == 2.0);
    GUARD_C_CHECK(wv[3] == 8.0);
    const tc_screw3 recovered_wv = tc_screw3_from_vector_wv_order(wv);
    GUARD_C_CHECK(recovered_wv.ang.y == screw.ang.y);
    GUARD_C_CHECK(recovered_wv.lin.y == screw.lin.y);

    const tc_pose3 frame = tc_pose3_new(tc_quat_identity(), TC_VEC3(3.0, -2.0, 1.0));
    const tc_screw3 twist = tc_screw3_transform_as_twist_by(screw, frame);
    const tc_screw3 recovered_twist = tc_screw3_inverse_transform_as_twist_by(twist, frame);
    GUARD_C_CHECK(recovered_twist.ang.x == screw.ang.x);
    GUARD_C_CHECK(recovered_twist.lin.x == screw.lin.x);

    return 0;
}
