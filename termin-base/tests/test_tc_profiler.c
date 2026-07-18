#include <stdio.h>
#include <string.h>

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

GUARD_C_TEST(test_profiler_native_capture_owns_bounded_complete_frames) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_capture* capture = tc_profiler_capture_create(3);
    GUARD_C_REQUIRE(capture != NULL);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 1);
    tc_profiler_capture_set_active(capture, true);

    int first_frame_number = -1;
    for (int index = 0; index < 4; ++index) {
        const tc_profiler_frame_info info = {
            1000.0 + index * 20.0,
            10.0 + index * 2.0,
            10.0,
            (double) index,
            index == 3 ? 1 : 0,
        };
        tc_profiler_begin_frame_with_info(&info);
        tc_frame_profile* current = tc_profiler_current_frame();
        GUARD_C_REQUIRE(current != NULL);
        if (index == 0) first_frame_number = current->frame_number;
        tc_profiler_begin_section("Root");
        tc_profiler_end_section();
        tc_profiler_end_frame();
    }

    GUARD_C_CHECK(tc_profiler_capture_count(capture) == 3);
    GUARD_C_CHECK(tc_profiler_capture_overwritten_count(capture) == 1);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 5);
    const tc_frame_profile* oldest = tc_profiler_capture_at(capture, 0);
    GUARD_C_REQUIRE(oldest != NULL);
    GUARD_C_CHECK(oldest->frame_number == first_frame_number + 1);
    GUARD_C_CHECK(oldest->section_count == 1);
    GUARD_C_CHECK(oldest->sections != NULL);
    GUARD_C_CHECK(strcmp(oldest->sections[0].name, "Root") == 0);
    GUARD_C_CHECK(tc_profiler_capture_find(capture, first_frame_number) == NULL);
    GUARD_C_CHECK(tc_profiler_capture_find(capture, first_frame_number + 3) != NULL);

    tc_profiler_history_range range;
    GUARD_C_REQUIRE(tc_profiler_capture_after(capture, first_frame_number - 1, &range));
    GUARD_C_CHECK(range.count == 3);
    GUARD_C_CHECK(range.dropped_count == 1);

    tc_profiler_frame_summary summary;
    GUARD_C_REQUIRE(tc_profiler_capture_summary_at(capture, 2, 1.25, &summary));
    GUARD_C_CHECK(summary.frame_number == first_frame_number + 3);
    GUARD_C_CHECK(summary.hitch);
    GUARD_C_CHECK(summary.has_pacing_gap);

    tc_profiler_statistics statistics;
    GUARD_C_REQUIRE(tc_profiler_capture_statistics(capture, -1, -1, 1.25, &statistics));
    GUARD_C_CHECK(statistics.frame_count == 3);
    GUARD_C_CHECK(statistics.max_interval_ms == 16.0);
    GUARD_C_CHECK(statistics.hitch_count == 2);
    GUARD_C_CHECK(statistics.overwritten_count == 1);

    tc_profiler_capture_set_active(capture, false);
    tc_profiler_begin_frame();
    tc_profiler_end_frame();
    GUARD_C_CHECK(tc_profiler_capture_count(capture) == 3);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 5);

    tc_profiler_capture_clear(capture);
    GUARD_C_CHECK(tc_profiler_capture_count(capture) == 0);
    GUARD_C_CHECK(tc_profiler_capture_overwritten_count(capture) == 0);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 6);
    tc_profiler_capture_destroy(capture);
    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_capture_records_frame_timing_without_section_profiling) {
    tc_profiler_set_enabled(false);
    tc_profiler_clear_history();
    tc_profiler_capture* capture = tc_profiler_capture_create(4);
    GUARD_C_REQUIRE(capture != NULL);
    tc_profiler_capture_set_active(capture, true);

    GUARD_C_CHECK(tc_profiler_frame_capture_enabled());
    GUARD_C_CHECK(!tc_profiler_enabled());
    GUARD_C_CHECK(!tc_profiler_capture_profiling(capture));

    tc_profiler_begin_frame();
    GUARD_C_CHECK(!tc_profiler_enabled());
    tc_profiler_begin_section("not-recorded");
    tc_profiler_end_section();
    // Enabling section profiling during a frame takes effect on the next
    // frame, keeping already-open begin/end pairs balanced.
    tc_profiler_capture_set_profiling(capture, true);
    GUARD_C_CHECK(!tc_profiler_enabled());
    tc_profiler_end_frame();

    const tc_frame_profile* timing_only = tc_profiler_capture_at(capture, 0);
    GUARD_C_REQUIRE(timing_only != NULL);
    GUARD_C_CHECK(!timing_only->sections_profiled);
    GUARD_C_CHECK(timing_only->section_count == 0);
    GUARD_C_CHECK(timing_only->active_ms >= 0.0);

    tc_profiler_begin_frame();
    GUARD_C_CHECK(tc_profiler_enabled());
    tc_profiler_begin_section("recorded");
    // Disabling during an open frame is also deferred until its end.
    tc_profiler_capture_set_profiling(capture, false);
    GUARD_C_CHECK(tc_profiler_enabled());
    tc_profiler_end_section();
    tc_profiler_end_frame();

    const tc_frame_profile* profiled = tc_profiler_capture_at(capture, 1);
    GUARD_C_REQUIRE(profiled != NULL);
    GUARD_C_CHECK(profiled->sections_profiled);
    GUARD_C_CHECK(profiled->section_count == 1);
    GUARD_C_CHECK(strcmp(profiled->sections[0].name, "recorded") == 0);

    GUARD_C_CHECK(!tc_profiler_enabled());
    tc_profiler_capture_set_active(capture, false);
    GUARD_C_CHECK(!tc_profiler_frame_capture_enabled());
    tc_profiler_capture_destroy(capture);
    tc_profiler_clear_history();
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_profiler_bounds_deeply_nested_sections);
    GUARD_C_RUN(test_profiler_preserves_raw_frame_timing_and_excludes_open_frame);
    GUARD_C_RUN(test_profiler_history_cursor_reports_ring_overwrite);
    GUARD_C_RUN(test_profiler_native_capture_owns_bounded_complete_frames);
    GUARD_C_RUN(test_capture_records_frame_timing_without_section_profiling);
    return GUARD_C_END();
}
