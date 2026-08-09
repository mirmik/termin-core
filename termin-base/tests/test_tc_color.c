#include <stddef.h>
#include <assert.h>

#include <geom/tc_color.h>

int main(void) {
    assert(sizeof(tc_srgb_color) == sizeof(float) * 4);
    assert(sizeof(tc_linear_color) == sizeof(float) * 4);
    assert(offsetof(tc_srgb_color, a) == sizeof(float) * 3);
    assert(offsetof(tc_linear_color, a) == sizeof(float) * 3);

    const tc_linear_color linear = tc_srgb_to_linear((tc_srgb_color){0.5f, 0.25f, 1.0f, 0.5f});
    assert(linear.r > 0.2140f && linear.r < 0.2141f);
    assert(linear.a == 0.5f);

    const tc_srgb_color encoded = tc_linear_to_srgb(linear);
    assert(encoded.r > 0.4999f && encoded.r < 0.5001f);
    assert(encoded.a == 0.5f);
    return 0;
}
