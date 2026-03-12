#include "tc_profiler.h"
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
    bool enabled;
    bool profile_components;
    bool detailed_rendering;
    int frame_count;
    tc_frame_profile* current_frame;
    double frame_start_time;
    int section_stack[TC_PROFILER_MAX_DEPTH];
    double section_start_times[TC_PROFILER_MAX_DEPTH];
    int stack_depth;
    tc_frame_profile history[PROFILER_HISTORY_SIZE];
    int history_start;
    int history_count;
} tc_profiler;

static tc_profiler g_profiler = {0};

void* tc_profiler_instance(void) {
    return &g_profiler;
}

bool tc_profiler_enabled(void) {
    return g_profiler.enabled;
}

void tc_profiler_set_enabled(bool enabled) {
    g_profiler.enabled = enabled;
    if (!enabled) {
        g_profiler.current_frame = NULL;
        g_profiler.stack_depth = 0;
    }
}

bool tc_profiler_profile_components(void) {
    return g_profiler.profile_components;
}

void tc_profiler_set_profile_components(bool enabled) {
    g_profiler.profile_components = enabled;
}

bool tc_profiler_detailed_rendering(void) {
    return g_profiler.detailed_rendering;
}

void tc_profiler_set_detailed_rendering(bool enabled) {
    g_profiler.detailed_rendering = enabled;
}

void tc_profiler_begin_frame(void) {
    if (!g_profiler.enabled) return;
    if (g_profiler.current_frame != NULL) return;

    int slot = (g_profiler.history_start + g_profiler.history_count) % PROFILER_HISTORY_SIZE;
    if (g_profiler.history_count == PROFILER_HISTORY_SIZE) {
        g_profiler.history_start = (g_profiler.history_start + 1) % PROFILER_HISTORY_SIZE;
    } else {
        g_profiler.history_count++;
    }

    tc_frame_profile* frame = &g_profiler.history[slot];
    memset(frame, 0, sizeof(tc_frame_profile));
    frame->frame_number = g_profiler.frame_count++;

    g_profiler.current_frame = frame;
    g_profiler.stack_depth = 0;
    g_profiler.frame_start_time = get_time_ms();
}

void tc_profiler_end_frame(void) {
    if (!g_profiler.enabled) return;
    if (g_profiler.current_frame == NULL) return;

    g_profiler.current_frame->total_ms = get_time_ms() - g_profiler.frame_start_time;
    g_profiler.current_frame = NULL;
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

void tc_profiler_begin_section(const char* name) {
    if (!g_profiler.enabled) return;
    if (g_profiler.current_frame == NULL) return;
    if (g_profiler.stack_depth >= TC_PROFILER_MAX_DEPTH) return;

    int parent_index = (g_profiler.stack_depth > 0)
        ? g_profiler.section_stack[g_profiler.stack_depth - 1]
        : -1;

    int section_idx = find_or_create_section(name, parent_index);
    if (section_idx < 0) return;

    g_profiler.section_stack[g_profiler.stack_depth] = section_idx;
    g_profiler.section_start_times[g_profiler.stack_depth] = get_time_ms();
    g_profiler.stack_depth++;
}

void tc_profiler_end_section(void) {
    if (!g_profiler.enabled) return;
    if (g_profiler.current_frame == NULL) return;
    if (g_profiler.stack_depth <= 0) return;

    g_profiler.stack_depth--;
    int section_idx = g_profiler.section_stack[g_profiler.stack_depth];
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
    return g_profiler.history_count;
}

tc_frame_profile* tc_profiler_history_at(int index) {
    if (index < 0 || index >= g_profiler.history_count) return NULL;
    int slot = (g_profiler.history_start + index) % PROFILER_HISTORY_SIZE;
    return &g_profiler.history[slot];
}

void tc_profiler_clear_history(void) {
    g_profiler.history_start = 0;
    g_profiler.history_count = 0;
}

int tc_profiler_frame_count(void) {
    return g_profiler.frame_count;
}
