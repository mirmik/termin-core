// tc_string.h - process-wide shared C string helpers.
#ifndef TCBASE_TC_STRING_H
#define TCBASE_TC_STRING_H

#include <tcbase/tcbase_api.h>

#ifdef __cplusplus
extern "C" {
#endif

// Intern a string in the process-wide table. Returned pointers are stable until
// tc_intern_cleanup() and can be compared by pointer for canonical identity.
// Thread-unsafe: call from the owning/runtime thread.
TCBASE_API const char* tc_intern_string(const char* s);
TCBASE_API void tc_intern_cleanup(void);

#ifdef __cplusplus
}
#endif

#endif // TCBASE_TC_STRING_H
