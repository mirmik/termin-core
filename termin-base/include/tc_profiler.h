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
    // Monotonic timestamp at which this frame started. The epoch is
    // intentionally unspecified; only differences between samples matter.
    double start_time_ms;
    // Time between this frame start and the previous frame start. Zero means
    // that no previous cadence sample was available.
    double interval_ms;
    // CPU wall time between profiler begin/end. total_ms is retained as the
    // compatibility name for the same value.
    double active_ms;
    double total_ms;
    double target_interval_ms;
    double deadline_lateness_ms;
    int missed_intervals;
    tc_section_timing sections[TC_PROFILER_MAX_SECTIONS];
    int section_count;
} tc_frame_profile;

typedef struct tc_profiler_frame_info {
    double start_time_ms;
    double interval_ms;
    double target_interval_ms;
    double deadline_lateness_ms;
    int missed_intervals;
} tc_profiler_frame_info;

// A stable description of the complete retained frames newer than a cursor.
// first_index/count address tc_profiler_history_at() in oldest-to-newest order.
// dropped_count is non-zero when frames after the cursor have already been
// overwritten by the bounded history ring.
typedef struct tc_profiler_history_range {
    int first_index;
    int count;
    int dropped_count;
    int oldest_frame_number;
    int newest_frame_number;
} tc_profiler_history_range;

TCBASE_API void* tc_profiler_instance(void);
TCBASE_API bool tc_profiler_enabled(void);
TCBASE_API void tc_profiler_set_enabled(bool enabled);
TCBASE_API bool tc_profiler_profile_components(void);
TCBASE_API void tc_profiler_set_profile_components(bool enabled);
TCBASE_API bool tc_profiler_detailed_rendering(void);
TCBASE_API void tc_profiler_set_detailed_rendering(bool enabled);
TCBASE_API void tc_profiler_begin_frame(void);
TCBASE_API void tc_profiler_begin_frame_with_info(const tc_profiler_frame_info* info);
TCBASE_API void tc_profiler_end_frame(void);
TCBASE_API void tc_profiler_begin_section(const char* name);
// Begin a "muted" section — pushes a balanced stack entry but drops all
// timing (for the section and every nested begin_section inside it). Use
// it at the boundary where the caller has decided that this subtree of
// work should not show up in the profile tree, without spraying a flag
// check through every nested callee. Paired with the regular
// `tc_profiler_end_section()`.
TCBASE_API void tc_profiler_begin_section_muted(const char* name);
TCBASE_API void tc_profiler_end_section(void);
TCBASE_API tc_frame_profile* tc_profiler_current_frame(void);
TCBASE_API int tc_profiler_history_count(void);
TCBASE_API tc_frame_profile* tc_profiler_history_at(int index);
TCBASE_API bool tc_profiler_history_after(
    int last_frame_number,
    tc_profiler_history_range* out_range
);
TCBASE_API void tc_profiler_clear_history(void);
TCBASE_API int tc_profiler_frame_count(void);

#ifdef __cplusplus
}
#endif

#endif
