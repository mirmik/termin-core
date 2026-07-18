#include "tc_profiler.h"
#include "tcbase/tc_log.h"
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
static double get_time_ms(void) {
    static LARGE_INTEGER freq = {0};
    if (freq.QuadPart == 0) {
        QueryPerformanceFrequency(&freq);
    }
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return (double) now.QuadPart / (double) freq.QuadPart * 1000.0;
}
#else
#include <time.h>
static double get_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1000000.0;
}
#endif

#define PROFILER_HISTORY_SIZE 120

typedef struct {
    tc_frame_profile* frames;
    int capacity;
    int start;
    int count;
    int overwritten_count;
} tc_profile_ring;

struct tc_profiler_capture {
    tc_profile_ring ring;
    bool active;
    bool profiling;
    unsigned long long revision;
    struct tc_profiler_capture* next;
};

static void profile_frame_release(tc_frame_profile* frame) {
    if (!frame) return;
    free(frame->sections);
    memset(frame, 0, sizeof(*frame));
}

static bool profile_ring_init(tc_profile_ring* ring, int capacity) {
    if (!ring || capacity <= 0) return false;
    ring->frames = (tc_frame_profile*) calloc((size_t) capacity, sizeof(tc_frame_profile));
    if (!ring->frames) {
        tc_log(TC_LOG_ERROR,
            "tc_profiler: failed to allocate capture ring with capacity %d", capacity);
        return false;
    }
    ring->capacity = capacity;
    return true;
}

static void profile_ring_clear(tc_profile_ring* ring) {
    if (!ring || !ring->frames) return;
    for (int index = 0; index < ring->capacity; ++index) {
        profile_frame_release(&ring->frames[index]);
    }
    ring->start = 0;
    ring->count = 0;
    ring->overwritten_count = 0;
}

static void profile_ring_destroy(tc_profile_ring* ring) {
    if (!ring) return;
    profile_ring_clear(ring);
    free(ring->frames);
    memset(ring, 0, sizeof(*ring));
}

static tc_frame_profile* profile_ring_at(const tc_profile_ring* ring, int index) {
    if (!ring || !ring->frames || index < 0 || index >= ring->count) return NULL;
    int slot = (ring->start + index) % ring->capacity;
    return &ring->frames[slot];
}

static bool profile_ring_append(tc_profile_ring* ring, const tc_frame_profile* source) {
    if (!ring || !ring->frames || !source) return false;

    tc_section_timing* sections = NULL;
    if (source->section_count > 0) {
        sections = (tc_section_timing*) malloc(
            sizeof(tc_section_timing) * (size_t) source->section_count
        );
        if (!sections) {
            tc_log(TC_LOG_ERROR,
                "tc_profiler: failed to copy %d frame sections", source->section_count);
            return false;
        }
        memcpy(sections, source->sections,
               sizeof(tc_section_timing) * (size_t) source->section_count);
    }

    int slot;
    if (ring->count == ring->capacity) {
        slot = ring->start;
        ring->start = (ring->start + 1) % ring->capacity;
        ring->overwritten_count++;
    } else {
        slot = (ring->start + ring->count) % ring->capacity;
        ring->count++;
    }
    profile_frame_release(&ring->frames[slot]);
    ring->frames[slot] = *source;
    ring->frames[slot].sections = sections;
    return true;
}

static bool profile_ring_after(
    const tc_profile_ring* ring,
    int last_frame_number,
    tc_profiler_history_range* out_range
) {
    if (!out_range) {
        tc_log(TC_LOG_ERROR, "tc_profiler history range output must not be NULL");
        return false;
    }
    memset(out_range, 0, sizeof(*out_range));
    out_range->oldest_frame_number = -1;
    out_range->newest_frame_number = -1;
    if (!ring || ring->count <= 0) return true;

    tc_frame_profile* oldest = profile_ring_at(ring, 0);
    tc_frame_profile* newest = profile_ring_at(ring, ring->count - 1);
    if (!oldest || !newest) {
        tc_log(TC_LOG_ERROR, "tc_profiler: inconsistent profile ring");
        return false;
    }
    out_range->oldest_frame_number = oldest->frame_number;
    out_range->newest_frame_number = newest->frame_number;
    if (last_frame_number >= 0 && oldest->frame_number > last_frame_number + 1) {
        out_range->dropped_count = oldest->frame_number - last_frame_number - 1;
    }
    int first_index = ring->count;
    for (int index = 0; index < ring->count; ++index) {
        tc_frame_profile* frame = profile_ring_at(ring, index);
        if (frame && frame->frame_number > last_frame_number) {
            first_index = index;
            break;
        }
    }
    out_range->first_index = first_index;
    out_range->count = ring->count - first_index;
    return true;
}

typedef struct {
    bool enabled_requested;
    bool sections_enabled;
    bool frame_capture_enabled;
    bool current_frame_profiles_sections;
    int frame_count;
    tc_frame_profile* current_frame;
    double frame_start_time;
    double previous_frame_start_time;
    bool has_previous_frame_start_time;
    int section_stack[TC_PROFILER_MAX_DEPTH];
    double section_start_times[TC_PROFILER_MAX_DEPTH];
    int stack_depth;
    // Number of balanced nested sections beyond section_stack's fixed
    // capacity. They are deliberately not recorded, but must still be
    // counted so their end_section calls cannot pop a valid stored section.
    int overflow_depth;
    // stack_depth at which the outermost muted section was opened.
    // While stack_depth >= muted_depth, every begin_section is treated
    // as a sentinel (no recording) so callees inside don't need to
    // know they're inside a muted subtree. -1 means "not muted".
    int muted_depth;
    tc_frame_profile current_frame_storage;
    tc_section_timing current_sections[TC_PROFILER_MAX_SECTIONS];
    tc_profile_ring history;
    tc_profiler_capture* captures;
} tc_profiler;

static tc_profiler g_profiler = {0};

static void profiler_refresh_enabled(void) {
    bool capture_active = false;
    bool capture_profiling = false;
    for (tc_profiler_capture* capture = g_profiler.captures;
         capture != NULL;
         capture = capture->next) {
        if (capture->active) {
            capture_active = true;
            if (capture->profiling) capture_profiling = true;
        }
    }
    g_profiler.sections_enabled =
        g_profiler.enabled_requested || capture_profiling;
    g_profiler.frame_capture_enabled =
        g_profiler.enabled_requested || capture_active;
}

void* tc_profiler_instance(void) {
    return &g_profiler;
}

bool tc_profiler_enabled(void) {
    return g_profiler.current_frame
        ? g_profiler.current_frame_profiles_sections
        : g_profiler.sections_enabled;
}

void tc_profiler_set_enabled(bool enabled) {
    g_profiler.enabled_requested = enabled;
    profiler_refresh_enabled();
}

bool tc_profiler_frame_capture_enabled(void) {
    return g_profiler.frame_capture_enabled;
}

void tc_profiler_begin_frame_with_info(const tc_profiler_frame_info* info) {
    if (!g_profiler.frame_capture_enabled) return;
    if (g_profiler.current_frame != NULL) {
        tc_log(TC_LOG_ERROR,
            "tc_profiler_begin_frame: previous frame is still open "
            "(stack_depth=%d). Nested/duplicate begin_frame call — check "
            "the caller. The existing frame is kept.",
            g_profiler.stack_depth);
        return;
    }

    tc_frame_profile* frame = &g_profiler.current_frame_storage;
    memset(frame, 0, sizeof(*frame));
    frame->sections = g_profiler.current_sections;
    frame->frame_number = g_profiler.frame_count++;
    frame->sections_profiled = g_profiler.sections_enabled;

    const double measured_start_time = get_time_ms();
    frame->start_time_ms = info ? info->start_time_ms : measured_start_time;
    if (info) {
        frame->interval_ms = info->interval_ms;
        frame->target_interval_ms = info->target_interval_ms;
        frame->deadline_lateness_ms = info->deadline_lateness_ms;
        frame->missed_intervals = info->missed_intervals;
    } else if (g_profiler.has_previous_frame_start_time) {
        frame->interval_ms = measured_start_time - g_profiler.previous_frame_start_time;
    }
    g_profiler.previous_frame_start_time = frame->start_time_ms;
    g_profiler.has_previous_frame_start_time = true;

    g_profiler.current_frame = frame;
    g_profiler.current_frame_profiles_sections = frame->sections_profiled;
    g_profiler.stack_depth = 0;
    g_profiler.overflow_depth = 0;
    g_profiler.muted_depth = -1;
    g_profiler.frame_start_time = measured_start_time;
}

void tc_profiler_begin_frame(void) {
    tc_profiler_begin_frame_with_info(NULL);
}

void tc_profiler_end_frame(void) {
    if (g_profiler.current_frame == NULL) {
        if (!g_profiler.frame_capture_enabled) return;
        tc_log(TC_LOG_ERROR,
            "tc_profiler_end_frame: no frame is open. Unbalanced "
            "begin_frame/end_frame pairing — check the caller.");
        return;
    }

    tc_frame_profile* completed = g_profiler.current_frame;
    completed->active_ms = get_time_ms() - g_profiler.frame_start_time;
    completed->total_ms = completed->active_ms;
    if (!g_profiler.history.frames &&
        !profile_ring_init(&g_profiler.history, PROFILER_HISTORY_SIZE)) {
        g_profiler.current_frame = NULL;
        g_profiler.current_frame_profiles_sections = false;
        return;
    }
    profile_ring_append(&g_profiler.history, completed);
    for (tc_profiler_capture* capture = g_profiler.captures;
         capture != NULL;
         capture = capture->next) {
        if (capture->active && profile_ring_append(&capture->ring, completed)) {
            capture->revision++;
        }
    }
    g_profiler.current_frame = NULL;
    g_profiler.current_frame_profiles_sections = false;
}

static int find_or_create_section(const char* name, int parent_index) {
    tc_frame_profile* frame = g_profiler.current_frame;

    int first_child = (parent_index >= 0) ? frame->sections[parent_index].first_child : -1;

    if (parent_index < 0) {
        for (int i = 0; i < frame->section_count; i++) {
            if (frame->sections[i].parent_index == -1 &&
                strcmp(frame->sections[i].name, name) == 0) {
                return i;
            }
        }
    } else {
        int idx = first_child;
        while (idx >= 0) {
            if (strcmp(frame->sections[idx].name, name) == 0) {
                return idx;
            }
            idx = frame->sections[idx].next_sibling;
        }
    }

    if (frame->section_count >= TC_PROFILER_MAX_SECTIONS) {
        static int s_overflow_logged = 0;
        if (!s_overflow_logged) {
            tc_log(TC_LOG_WARN,
                "tc_profiler: frame section count hit TC_PROFILER_MAX_SECTIONS=%d "
                "(dropped section: %s). Raise the cap in tc_profiler.h or shorten "
                "the pass list. Subsequent overflows are silenced.",
                TC_PROFILER_MAX_SECTIONS, name);
            s_overflow_logged = 1;
        }
        return -1;
    }

    int new_idx = frame->section_count++;
    tc_section_timing* section = &frame->sections[new_idx];

    strncpy(section->name, name, TC_PROFILER_MAX_NAME_LEN - 1);
    section->name[TC_PROFILER_MAX_NAME_LEN - 1] = '\0';
    section->cpu_ms = 0.0;
    section->children_ms = 0.0;
    section->call_count = 0;
    section->parent_index = parent_index;
    section->first_child = -1;
    section->next_sibling = -1;

    if (parent_index >= 0) {
        tc_section_timing* parent = &frame->sections[parent_index];
        if (parent->first_child < 0) {
            parent->first_child = new_idx;
        } else {
            int last = parent->first_child;
            while (frame->sections[last].next_sibling >= 0) {
                last = frame->sections[last].next_sibling;
            }
            frame->sections[last].next_sibling = new_idx;
        }
    }

    return new_idx;
}

static void begin_section_internal(const char* name, bool muted) {
    if (!g_profiler.current_frame_profiles_sections) return;
    if (g_profiler.current_frame == NULL) return;
    if (g_profiler.stack_depth >= TC_PROFILER_MAX_DEPTH) {
        static int s_depth_logged = 0;
        if (!s_depth_logged) {
            tc_log(TC_LOG_WARN,
                "tc_profiler: nesting depth exceeded TC_PROFILER_MAX_DEPTH=%d "
                "(dropped section: %s). Raise the cap in tc_profiler.h.",
                TC_PROFILER_MAX_DEPTH, name);
            s_depth_logged = 1;
        }
        // Do not touch the fixed arrays: their final slot contains the
        // deepest valid section. Count overflow separately so each matching
        // end_section is harmless and valid parent timing stays intact.
        g_profiler.overflow_depth++;
        return;
    }

    // Mute propagation: if we're already inside a muted subtree or the
    // caller is opening a new muted scope, push a sentinel and skip
    // recording. The first muted level latches muted_depth so end_section
    // can clear it on the matching pop.
    const bool already_muted = g_profiler.muted_depth >= 0;
    if (already_muted || muted) {
        if (muted && !already_muted) {
            g_profiler.muted_depth = g_profiler.stack_depth;
        }
        g_profiler.section_stack[g_profiler.stack_depth] = -1;
        g_profiler.section_start_times[g_profiler.stack_depth] = 0.0;
        g_profiler.stack_depth++;
        return;
    }

    int parent_index = (g_profiler.stack_depth > 0)
        ? g_profiler.section_stack[g_profiler.stack_depth - 1]
        : -1;

    int section_idx = find_or_create_section(name, parent_index);

    // Push even on overflow (section_idx == -1). end_section checks for
    // the sentinel and skips accounting. Without this the begin/end pairs
    // go out of sync and every subsequent end_section closes somebody
    // else's section — cpu_ms values get corrupted silently.
    g_profiler.section_stack[g_profiler.stack_depth] = section_idx;
    g_profiler.section_start_times[g_profiler.stack_depth] = get_time_ms();
    g_profiler.stack_depth++;
}

void tc_profiler_begin_section(const char* name) {
    begin_section_internal(name, false);
}

void tc_profiler_begin_section_muted(const char* name) {
    begin_section_internal(name, true);
}

void tc_profiler_end_section(void) {
    if (!g_profiler.current_frame_profiles_sections) return;
    if (g_profiler.current_frame == NULL) return;
    if (g_profiler.overflow_depth > 0) {
        g_profiler.overflow_depth--;
        return;
    }
    if (g_profiler.stack_depth <= 0) return;

    g_profiler.stack_depth--;

    // If we just exited the mute scope, clear the latch so the next
    // begin_section at this depth records normally again.
    if (g_profiler.muted_depth >= 0 &&
        g_profiler.stack_depth == g_profiler.muted_depth) {
        g_profiler.muted_depth = -1;
    }

    int section_idx = g_profiler.section_stack[g_profiler.stack_depth];
    // Sentinel (-1) means begin_section was muted or overflowed — skip
    // accounting.
    if (section_idx < 0) return;

    double elapsed = get_time_ms() - g_profiler.section_start_times[g_profiler.stack_depth];

    tc_section_timing* section = &g_profiler.current_frame->sections[section_idx];
    section->cpu_ms += elapsed;
    section->call_count++;

    if (section->parent_index >= 0) {
        tc_section_timing* parent = &g_profiler.current_frame->sections[section->parent_index];
        parent->children_ms += elapsed;
    }
}

tc_frame_profile* tc_profiler_current_frame(void) {
    return g_profiler.current_frame;
}

int tc_profiler_history_count(void) {
    return g_profiler.history.count;
}

tc_frame_profile* tc_profiler_history_at(int index) {
    return profile_ring_at(&g_profiler.history, index);
}

bool tc_profiler_history_after(
    int last_frame_number,
    tc_profiler_history_range* out_range
) {
    return profile_ring_after(&g_profiler.history, last_frame_number, out_range);
}

void tc_profiler_clear_history(void) {
    profile_ring_clear(&g_profiler.history);
    g_profiler.has_previous_frame_start_time = false;
}

int tc_profiler_frame_count(void) {
    return g_profiler.frame_count;
}

tc_profiler_capture* tc_profiler_capture_create(int capacity) {
    if (capacity <= 0) {
        tc_log(TC_LOG_ERROR,
            "tc_profiler_capture_create: capacity must be positive (got %d)", capacity);
        return NULL;
    }
    tc_profiler_capture* capture = (tc_profiler_capture*) calloc(1, sizeof(*capture));
    if (!capture) {
        tc_log(TC_LOG_ERROR, "tc_profiler_capture_create: allocation failed");
        return NULL;
    }
    if (!profile_ring_init(&capture->ring, capacity)) {
        free(capture);
        return NULL;
    }
    capture->next = g_profiler.captures;
    capture->revision = 1;
    g_profiler.captures = capture;
    return capture;
}

void tc_profiler_capture_destroy(tc_profiler_capture* capture) {
    if (!capture) return;
    tc_profiler_capture** link = &g_profiler.captures;
    while (*link && *link != capture) link = &(*link)->next;
    if (*link != capture) {
        tc_log(TC_LOG_ERROR,
            "tc_profiler_capture_destroy: capture is not registered");
        return;
    }
    *link = capture->next;
    const bool was_active = capture->active;
    profile_ring_destroy(&capture->ring);
    free(capture);
    if (was_active) profiler_refresh_enabled();
}

void tc_profiler_capture_set_active(tc_profiler_capture* capture, bool active) {
    if (!capture || capture->active == active) return;
    capture->active = active;
    profiler_refresh_enabled();
}

bool tc_profiler_capture_active(const tc_profiler_capture* capture) {
    return capture && capture->active;
}

void tc_profiler_capture_set_profiling(
    tc_profiler_capture* capture,
    bool profiling
) {
    if (!capture || capture->profiling == profiling) return;
    capture->profiling = profiling;
    profiler_refresh_enabled();
}

bool tc_profiler_capture_profiling(const tc_profiler_capture* capture) {
    return capture && capture->profiling;
}

void tc_profiler_capture_clear(tc_profiler_capture* capture) {
    if (!capture) return;
    profile_ring_clear(&capture->ring);
    capture->revision++;
}

int tc_profiler_capture_count(const tc_profiler_capture* capture) {
    return capture ? capture->ring.count : 0;
}

int tc_profiler_capture_overwritten_count(const tc_profiler_capture* capture) {
    return capture ? capture->ring.overwritten_count : 0;
}

unsigned long long tc_profiler_capture_revision(const tc_profiler_capture* capture) {
    return capture ? capture->revision : 0;
}

const tc_frame_profile* tc_profiler_capture_at(
    const tc_profiler_capture* capture,
    int index
) {
    return capture ? profile_ring_at(&capture->ring, index) : NULL;
}

const tc_frame_profile* tc_profiler_capture_find(
    const tc_profiler_capture* capture,
    int frame_number
) {
    if (!capture) return NULL;
    for (int index = 0; index < capture->ring.count; ++index) {
        tc_frame_profile* frame = profile_ring_at(&capture->ring, index);
        if (frame && frame->frame_number == frame_number) return frame;
    }
    return NULL;
}

bool tc_profiler_capture_after(
    const tc_profiler_capture* capture,
    int last_frame_number,
    tc_profiler_history_range* out_range
) {
    return profile_ring_after(
        capture ? &capture->ring : NULL,
        last_frame_number,
        out_range
    );
}

static bool frame_is_hitch(const tc_frame_profile* frame, double hitch_ratio) {
    return frame && (
        frame->missed_intervals > 0 ||
        (frame->target_interval_ms > 0.0 &&
         frame->interval_ms > frame->target_interval_ms * hitch_ratio)
    );
}

bool tc_profiler_capture_summary_at(
    const tc_profiler_capture* capture,
    int index,
    double hitch_ratio,
    tc_profiler_frame_summary* out_summary
) {
    if (!capture || !out_summary || hitch_ratio <= 1.0) {
        tc_log(TC_LOG_ERROR, "tc_profiler_capture_summary_at: invalid argument");
        return false;
    }
    const tc_frame_profile* frame = tc_profiler_capture_at(capture, index);
    if (!frame) return false;
    memset(out_summary, 0, sizeof(*out_summary));
    out_summary->frame_number = frame->frame_number;
    out_summary->start_time_ms = frame->start_time_ms;
    out_summary->interval_ms = frame->interval_ms;
    out_summary->active_ms = frame->active_ms;
    out_summary->target_interval_ms = frame->target_interval_ms;
    out_summary->deadline_lateness_ms = frame->deadline_lateness_ms;
    out_summary->missed_intervals = frame->missed_intervals;
    out_summary->hitch = frame_is_hitch(frame, hitch_ratio);
    if (index > 0) {
        const tc_frame_profile* previous = tc_profiler_capture_at(capture, index - 1);
        out_summary->gap_before =
            previous && frame->frame_number != previous->frame_number + 1;
        if (previous && !out_summary->gap_before && frame->interval_ms > 0.0) {
            out_summary->pacing_gap_ms = frame->interval_ms - previous->active_ms;
            if (out_summary->pacing_gap_ms < 0.0) out_summary->pacing_gap_ms = 0.0;
            out_summary->has_pacing_gap = true;
        }
    }
    return true;
}

static int compare_doubles(const void* left, const void* right) {
    const double a = *(const double*) left;
    const double b = *(const double*) right;
    return (a > b) - (a < b);
}

static double percentile_sorted(const double* values, int count, double quantile) {
    if (!values || count <= 0) return 0.0;
    const double position = (double) (count - 1) * quantile;
    const int lower = (int) position;
    const int upper = lower + 1 < count ? lower + 1 : lower;
    const double fraction = position - (double) lower;
    return values[lower] * (1.0 - fraction) + values[upper] * fraction;
}

bool tc_profiler_capture_statistics(
    const tc_profiler_capture* capture,
    int start_frame_number,
    int end_frame_number,
    double hitch_ratio,
    tc_profiler_statistics* out_statistics
) {
    if (!capture || !out_statistics || hitch_ratio <= 1.0) {
        tc_log(TC_LOG_ERROR, "tc_profiler_capture_statistics: invalid argument");
        return false;
    }
    memset(out_statistics, 0, sizeof(*out_statistics));
    out_statistics->overwritten_count = capture->ring.overwritten_count;
    double* intervals = NULL;
    if (capture->ring.count > 0) {
        intervals = (double*) malloc(sizeof(double) * (size_t) capture->ring.count);
        if (!intervals) {
            tc_log(TC_LOG_ERROR, "tc_profiler_capture_statistics: allocation failed");
            return false;
        }
    }
    int interval_count = 0;
    for (int index = 0; index < capture->ring.count; ++index) {
        const tc_frame_profile* frame = tc_profiler_capture_at(capture, index);
        if (!frame ||
            (start_frame_number >= 0 && frame->frame_number < start_frame_number) ||
            (end_frame_number >= 0 && frame->frame_number > end_frame_number)) {
            continue;
        }
        out_statistics->frame_count++;
        if (frame->interval_ms > 0.0) intervals[interval_count++] = frame->interval_ms;
        if (frame->interval_ms > out_statistics->max_interval_ms) {
            out_statistics->max_interval_ms = frame->interval_ms;
        }
        if (frame->active_ms > out_statistics->max_active_ms) {
            out_statistics->max_active_ms = frame->active_ms;
        }
        if (frame->deadline_lateness_ms > out_statistics->max_lateness_ms) {
            out_statistics->max_lateness_ms = frame->deadline_lateness_ms;
        }
        if (frame_is_hitch(frame, hitch_ratio)) out_statistics->hitch_count++;
    }
    if (interval_count > 0) {
        qsort(intervals, (size_t) interval_count, sizeof(double), compare_doubles);
        out_statistics->interval_p50_ms = percentile_sorted(intervals, interval_count, 0.50);
        out_statistics->interval_p95_ms = percentile_sorted(intervals, interval_count, 0.95);
        out_statistics->interval_p99_ms = percentile_sorted(intervals, interval_count, 0.99);
    }
    free(intervals);
    return true;
}
