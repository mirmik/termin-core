#include "guard_c.h"

#include <stdint.h>

#include <tcbase/tc_tensor.h>

GUARD_C_TEST(test_tc_tensor_owned_contiguous) {
    size_t shape[2] = {2, 3};
    tc_tensor tensor = tc_tensor_empty();
    GUARD_C_REQUIRE(tc_tensor_init_owned(&tensor, TC_DTYPE_F32, 2, shape, 0));

    GUARD_C_CHECK(tc_tensor_is_valid(&tensor));
    GUARD_C_CHECK(tc_tensor_is_c_contiguous(&tensor));
    GUARD_C_CHECK_EQ_SIZE(6, tc_tensor_element_count(&tensor));
    GUARD_C_CHECK_EQ_SIZE(24, tc_tensor_contiguous_byte_size(&tensor));
    GUARD_C_CHECK(tensor.strides[0] == 12);
    GUARD_C_CHECK(tensor.strides[1] == 4);

    float* values = (float*)tensor.data;
    values[5] = 42.0f;
    GUARD_C_CHECK(values[5] == 42.0f);

    tc_tensor_free(&tensor);
    GUARD_C_CHECK_FALSE(tc_tensor_is_valid(&tensor));
    return 0;
}

GUARD_C_TEST(test_tc_tensor_borrowed_strided_copy) {
    float interleaved[] = {
        1.0f, 10.0f,
        2.0f, 20.0f,
        3.0f, 30.0f,
    };
    size_t shape[2] = {3, 1};
    ptrdiff_t strides[2] = {8, 4};

    tc_tensor view = tc_tensor_empty();
    GUARD_C_REQUIRE(tc_tensor_init_borrowed(
        &view,
        interleaved,
        TC_DTYPE_F32,
        2,
        shape,
        strides,
        TC_TENSOR_READONLY));

    GUARD_C_CHECK(tc_tensor_is_valid(&view));
    GUARD_C_CHECK(tc_tensor_is_readonly(&view));
    GUARD_C_CHECK_FALSE(tc_tensor_is_c_contiguous(&view));

    tc_tensor copy = tc_tensor_empty();
    GUARD_C_REQUIRE(tc_tensor_copy_contiguous(&copy, &view));
    GUARD_C_CHECK(tc_tensor_is_c_contiguous(&copy));

    float* values = (float*)copy.data;
    GUARD_C_CHECK(values[0] == 1.0f);
    GUARD_C_CHECK(values[1] == 2.0f);
    GUARD_C_CHECK(values[2] == 3.0f);

    tc_tensor_free(&copy);
    tc_tensor_free(&view);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_tc_tensor_owned_contiguous);
    GUARD_C_RUN(test_tc_tensor_borrowed_strided_copy);
    return GUARD_C_END();
}
