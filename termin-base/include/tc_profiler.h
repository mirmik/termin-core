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
    // True when hierarchical section timings were collected for this frame.
    // Frame cadence/active timing may be captured with this disabled.
    bool sections_profiled;
    // Completed frames own a compact allocation containing exactly
    // section_count entries. The currently open frame points at profiler-owned
    // scratch storage. Callers must never retain this pointer after the owning
    // history/capture is cleared or destroyed.
    tc_section_timing* sections;
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

typedef struct tc_profiler_capture tc_profiler_capture;

typedef struct tc_profiler_frame_summary {
    int frame_number;
    double start_time_ms;
    double interval_ms;
    double active_ms;
    double target_interval_ms;
    double deadline_lateness_ms;
    int missed_intervals;
    double pacing_gap_ms;
    bool has_pacing_gap;
    bool gap_before;
    bool hitch;
} tc_profiler_frame_summary;

typedef struct tc_profiler_statistics {
    int frame_count;
    double interval_p50_ms;
    double interval_p95_ms;
    double interval_p99_ms;
    double max_interval_ms;
    double max_active_ms;
    double max_lateness_ms;
    int hitch_count;
    int overwritten_count;
} tc_profiler_statistics;

TCBASE_API void* tc_profiler_instance(void);
// Whether hierarchical section instrumentation is enabled for the current
// frame (or requested for the next frame when no frame is open).
TCBASE_API bool tc_profiler_enabled(void);
TCBASE_API void tc_profiler_set_enabled(bool enabled);
// Frame timing is cheaper than hierarchical section profiling and can remain
// active for native capture subscribers while tc_profiler_enabled() is false.
TCBASE_API bool tc_profiler_frame_capture_enabled(void);
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

// Independent native capture buffers subscribe directly to completed frames.
// They retain compact C-owned copies and may be paused without affecting the
// process-global short history or another profiler frontend.
TCBASE_API tc_profiler_capture* tc_profiler_capture_create(int capacity);
TCBASE_API void tc_profiler_capture_destroy(tc_profiler_capture* capture);
TCBASE_API void tc_profiler_capture_set_active(tc_profiler_capture* capture, bool active);
TCBASE_API bool tc_profiler_capture_active(const tc_profiler_capture* capture);
TCBASE_API void tc_profiler_capture_set_profiling(
    tc_profiler_capture* capture,
    bool profiling
);
TCBASE_API bool tc_profiler_capture_profiling(const tc_profiler_capture* capture);
TCBASE_API void tc_profiler_capture_clear(tc_profiler_capture* capture);
TCBASE_API int tc_profiler_capture_count(const tc_profiler_capture* capture);
TCBASE_API int tc_profiler_capture_overwritten_count(const tc_profiler_capture* capture);
TCBASE_API unsigned long long tc_profiler_capture_revision(
    const tc_profiler_capture* capture
);
TCBASE_API const tc_frame_profile* tc_profiler_capture_at(
    const tc_profiler_capture* capture,
    int index
);
TCBASE_API const tc_frame_profile* tc_profiler_capture_find(
    const tc_profiler_capture* capture,
    int frame_number
);
TCBASE_API bool tc_profiler_capture_after(
    const tc_profiler_capture* capture,
    int last_frame_number,
    tc_profiler_history_range* out_range
);
TCBASE_API bool tc_profiler_capture_summary_at(
    const tc_profiler_capture* capture,
    int index,
    double hitch_ratio,
    tc_profiler_frame_summary* out_summary
);
TCBASE_API bool tc_profiler_capture_statistics(
    const tc_profiler_capture* capture,
    int start_frame_number,
    int end_frame_number,
    double hitch_ratio,
    tc_profiler_statistics* out_statistics
);

#ifdef __cplusplus
}
#endif

#endif
