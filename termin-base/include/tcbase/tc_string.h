// tc_string.h - process-wide shared C string helpers.
#ifndef TCBASE_TC_STRING_H
#define TCBASE_TC_STRING_H

#include <tcbase/tcbase_api.h>

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_intern_string_stats {
    size_t entry_count;
    size_t bucket_count;
    size_t non_empty_bucket_count;
    size_t max_bucket_depth;
} tc_intern_string_stats;

typedef void (*tc_intern_string_foreach_fn)(
    const char* string,
    size_t bucket_index,
    size_t depth_in_bucket,
    void* user_data
);

// Intern a string in the process-wide table. Returned pointers are stable until
// tc_intern_cleanup() and can be compared by pointer for canonical identity.
// Thread-unsafe: call from the owning/runtime thread.
TCBASE_API const char* tc_intern_string(const char* s);
TCBASE_API void tc_intern_cleanup(void);

TCBASE_API tc_intern_string_stats tc_intern_string_get_stats(void);
TCBASE_API void tc_intern_string_foreach(tc_intern_string_foreach_fn callback, void* user_data);

#ifdef __cplusplus
}
#endif

#endif // TCBASE_TC_STRING_H
