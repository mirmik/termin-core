#include <stdio.h>

#include "guard_c.h"

#include <tc_profiler.h>

GUARD_C_TEST(test_profiler_bounds_deeply_nested_sections) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_begin_frame();

    for (int i = 0; i < 32; ++i) {
        char name[32];
        snprintf(name, sizeof(name), "nested-%d", i);
        tc_profiler_begin_section(name);
    }
    for (int i = 0; i < 32; ++i) {
        tc_profiler_end_section();
    }
    tc_profiler_end_frame();

    tc_frame_profile* frame = tc_profiler_history_at(0);
    GUARD_C_REQUIRE(frame != NULL);
    GUARD_C_CHECK(frame->section_count == TC_PROFILER_MAX_DEPTH);
    for (int i = 0; i < TC_PROFILER_MAX_DEPTH; ++i) {
        GUARD_C_CHECK(frame->sections[i].call_count == 1);
        GUARD_C_CHECK(frame->sections[i].parent_index == i - 1);
    }

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_profiler_bounds_deeply_nested_sections);
    return GUARD_C_END();
}
