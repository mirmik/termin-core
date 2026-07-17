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

GUARD_C_TEST(test_profiler_preserves_raw_frame_timing_and_excludes_open_frame) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    const tc_profiler_frame_info info = {
        1000.0,
        17.25,
        16.0,
        1.25,
        0,
    };
    tc_profiler_begin_frame_with_info(&info);
    tc_frame_profile* current = tc_profiler_current_frame();
    GUARD_C_REQUIRE(current != NULL);
    const int frame_number = current->frame_number;
    GUARD_C_CHECK(current->start_time_ms == 1000.0);
    GUARD_C_CHECK(current->interval_ms == 17.25);
    GUARD_C_CHECK(current->target_interval_ms == 16.0);
    GUARD_C_CHECK(current->deadline_lateness_ms == 1.25);

    tc_profiler_history_range open_range;
    GUARD_C_REQUIRE(tc_profiler_history_after(frame_number - 1, &open_range));
    GUARD_C_CHECK(open_range.count == 0);

    tc_profiler_end_frame();
    tc_frame_profile* complete = tc_profiler_history_at(0);
    GUARD_C_REQUIRE(complete != NULL);
    GUARD_C_CHECK(complete->active_ms >= 0.0);
    GUARD_C_CHECK(complete->active_ms == complete->total_ms);

    tc_profiler_history_range complete_range;
    GUARD_C_REQUIRE(tc_profiler_history_after(frame_number - 1, &complete_range));
    GUARD_C_CHECK(complete_range.first_index == 0);
    GUARD_C_CHECK(complete_range.count == 1);
    GUARD_C_CHECK(complete_range.dropped_count == 0);
    GUARD_C_CHECK(complete_range.oldest_frame_number == frame_number);
    GUARD_C_CHECK(complete_range.newest_frame_number == frame_number);

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_profiler_history_cursor_reports_ring_overwrite) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    int first_frame_number = -1;
    for (int index = 0; index < 125; ++index) {
        tc_profiler_begin_frame();
        tc_frame_profile* current = tc_profiler_current_frame();
        GUARD_C_REQUIRE(current != NULL);
        if (index == 0) first_frame_number = current->frame_number;
        tc_profiler_end_frame();
    }

    tc_profiler_history_range range;
    GUARD_C_REQUIRE(tc_profiler_history_after(first_frame_number - 1, &range));
    GUARD_C_CHECK(range.count == 120);
    GUARD_C_CHECK(range.dropped_count == 5);
    GUARD_C_CHECK(range.oldest_frame_number == first_frame_number + 5);
    GUARD_C_CHECK(range.newest_frame_number == first_frame_number + 124);

    tc_profiler_history_range tail;
    GUARD_C_REQUIRE(tc_profiler_history_after(first_frame_number + 120, &tail));
    GUARD_C_CHECK(tail.count == 4);
    GUARD_C_CHECK(tail.dropped_count == 0);
    GUARD_C_CHECK(tc_profiler_history_at(tail.first_index)->frame_number ==
                  first_frame_number + 121);

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_profiler_bounds_deeply_nested_sections);
    GUARD_C_RUN(test_profiler_preserves_raw_frame_timing_and_excludes_open_frame);
    GUARD_C_RUN(test_profiler_history_cursor_reports_ring_overwrite);
    return GUARD_C_END();
}
