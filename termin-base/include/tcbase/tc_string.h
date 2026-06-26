// tc_string.h - process-wide shared C string helpers.
#ifndef TCBASE_TC_STRING_H
#define TCBASE_TC_STRING_H

#include <tcbase/tcbase_api.h>

#ifdef __cplusplus
extern "C" {
#endif

TCBASE_API const char* tc_intern_string(const char* s);

#ifdef __cplusplus
}
#endif

#endif // TCBASE_TC_STRING_H
