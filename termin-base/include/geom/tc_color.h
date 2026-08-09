#ifndef TC_COLOR_H
#define TC_COLOR_H

#include <tcbase/tcbase_api.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_srgb_color {
    float r;
    float g;
    float b;
    float a;
} tc_srgb_color;

typedef struct tc_linear_color {
    float r;
    float g;
    float b;
    float a;
} tc_linear_color;

TCBASE_API tc_linear_color tc_srgb_to_linear(tc_srgb_color value);
TCBASE_API tc_srgb_color tc_linear_to_srgb(tc_linear_color value);

#ifdef __cplusplus
}
#endif

#endif
