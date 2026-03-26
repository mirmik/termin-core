// tc_profiler.h - Hierarchical profiler for timing code sections
#ifndef TC_PROFILER_H
#define TC_PROFILER_H

#include "tcbase/tcbase_api.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TC_PROFILER_MAX_DEPTH 16
#define TC_PROFILER_MAX_SECTIONS 256
#define TC_PROFILER_MAX_NAME_LEN 64

typedef struct tc_section_timing {
    char name[TC_PROFILER_MAX_NAME_LEN];
    double cpu_ms;
    double children_ms;
    int call_count;
    int parent_index;
    int first_child;
    int next_sibling;
} tc_section_timing;

typedef struct tc_frame_profile {
    int frame_number;
    double total_ms;
    tc_section_timing sections[TC_PROFILER_MAX_SECTIONS];
    int section_count;
} tc_frame_profile;

TCBASE_API void* tc_profiler_instance(void);
TCBASE_API bool tc_profiler_enabled(void);
TCBASE_API void tc_profiler_set_enabled(bool enabled);
TCBASE_API bool tc_profiler_profile_components(void);
TCBASE_API void tc_profiler_set_profile_components(bool enabled);
TCBASE_API bool tc_profiler_detailed_rendering(void);
TCBASE_API void tc_profiler_set_detailed_rendering(bool enabled);
TCBASE_API void tc_profiler_begin_frame(void);
TCBASE_API void tc_profiler_end_frame(void);
TCBASE_API void tc_profiler_begin_section(const char* name);
TCBASE_API void tc_profiler_end_section(void);
TCBASE_API tc_frame_profile* tc_profiler_current_frame(void);
TCBASE_API int tc_profiler_history_count(void);
TCBASE_API tc_frame_profile* tc_profiler_history_at(int index);
TCBASE_API void tc_profiler_clear_history(void);
TCBASE_API int tc_profiler_frame_count(void);

#ifdef __cplusplus
}
#endif

#endif
